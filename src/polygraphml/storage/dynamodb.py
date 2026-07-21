from __future__ import annotations

import builtins
import hashlib
import secrets
from collections.abc import Iterable, Sequence
from datetime import timedelta
from typing import Any, ClassVar, TypeVar

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pydantic import BaseModel

from polygraphml.domain.ids import new_id
from polygraphml.domain.models import (
    Artifact,
    Audit,
    AuditEvent,
    AuditReport,
    Correction,
    Evidence,
    Finding,
    Hypothesis,
    Project,
    Question,
    RepairBundle,
    Session,
    utc_now,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class DynamoRepository:
    """DynamoDB single-table repository for shared API/worker state."""

    _model_kinds: ClassVar[dict[type[BaseModel], str]] = {
        Project: "project",
        Artifact: "artifact",
        Audit: "audit",
        Question: "question",
        Hypothesis: "hypothesis",
        Evidence: "evidence",
        Finding: "finding",
        Correction: "correction",
        AuditReport: "report",
        RepairBundle: "repair_bundle",
    }
    _id_fields: ClassVar[dict[type[BaseModel], str]] = {
        Project: "project_id",
        Artifact: "artifact_id",
        Audit: "audit_id",
        Question: "question_id",
        Hypothesis: "hypothesis_id",
        Evidence: "evidence_id",
        Finding: "finding_id",
        Correction: "correction_id",
        AuditReport: "report_id",
        RepairBundle: "bundle_id",
    }

    def __init__(self, table_name: str, region: str, *, resource: Any | None = None) -> None:
        dynamodb = resource or boto3.resource("dynamodb", region_name=region)
        self.table = dynamodb.Table(table_name)

    def close(self) -> None:
        return None

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create_session(self, ttl_seconds: int) -> tuple[Session, str]:
        token = secrets.token_urlsafe(32)
        session = Session(
            session_id=new_id("ses"),
            token_hash=self.token_hash(token),
            expires_at=utc_now() + timedelta(seconds=ttl_seconds),
        )
        self.table.put_item(
            Item={
                "pk": "SESSION",
                "sk": session.session_id,
                "payload": session.model_dump_json(),
                "gsi2pk": f"TOKEN#{session.token_hash}",
                "gsi2sk": session.session_id,
                "expires_at_epoch": int(session.expires_at.timestamp()),
            }
        )
        return session, token

    def get_session_by_token(self, token: str) -> Session | None:
        response = self.table.query(
            IndexName="token-index",
            KeyConditionExpression=Key("gsi2pk").eq(f"TOKEN#{self.token_hash(token)}"),
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            return None
        session = Session.model_validate_json(items[0]["payload"])
        return session if session.expires_at > utc_now() else None

    @staticmethod
    def _parent_id(model: BaseModel) -> str | None:
        if isinstance(model, RepairBundle):
            return model.audit_id
        for name in ("project_id", "audit_id", "session_id"):
            value = getattr(model, name, None)
            if isinstance(value, str):
                return value
        return None

    def put(self, model: ModelT) -> ModelT:
        kind = self._model_kinds[type(model)]
        object_id = str(getattr(model, self._id_fields[type(model)]))
        assignments = ["payload = :payload", "updated_at = :updated"]
        values: dict[str, Any] = {
            ":payload": model.model_dump_json(),
            ":updated": utc_now().isoformat(),
        }
        parent_id = self._parent_id(model)
        if parent_id:
            assignments.extend(["gsi1pk = :parent", "gsi1sk = :parent_sort"])
            values.update({":parent": f"PARENT#{parent_id}", ":parent_sort": f"{kind}#{object_id}"})
        if isinstance(model, Audit):
            # Event sequence is advanced atomically by append_event. A stale audit
            # snapshot must never lower that counter during a retry/checkpoint write.
            assignments.append("event_sequence = if_not_exists(event_sequence, :sequence)")
            values[":sequence"] = model.last_event_sequence
        self.table.update_item(
            Key={"pk": f"OBJECT#{kind}", "sk": object_id},
            UpdateExpression="SET " + ", ".join(assignments),
            ExpressionAttributeValues=values,
        )
        return model

    def get(self, model_type: type[ModelT], object_id: str) -> ModelT | None:
        kind = self._model_kinds[model_type]
        response = self.table.get_item(
            Key={"pk": f"OBJECT#{kind}", "sk": object_id}, ConsistentRead=True
        )
        item = response.get("Item")
        return model_type.model_validate_json(item["payload"]) if item else None

    def list(self, model_type: type[ModelT], parent_id: str | None = None) -> builtins.list[ModelT]:
        kind = self._model_kinds[model_type]
        if parent_id is None:
            items = self._all_query(KeyConditionExpression=Key("pk").eq(f"OBJECT#{kind}"))
        else:
            items = self._all_query(
                IndexName="parent-index",
                KeyConditionExpression=Key("gsi1pk").eq(f"PARENT#{parent_id}")
                & Key("gsi1sk").begins_with(f"{kind}#"),
            )
        models = [model_type.model_validate_json(item["payload"]) for item in items]
        return sorted(models, key=lambda model: str(getattr(model, self._id_fields[model_type])))

    def _all_query(self, **kwargs: Any) -> builtins.list[dict[str, Any]]:
        items: builtins.list[dict[str, Any]] = []
        while True:
            response = self.table.query(**kwargs)
            items.extend(response.get("Items", []))
            key = response.get("LastEvaluatedKey")
            if not key:
                return items
            kwargs["ExclusiveStartKey"] = key

    def count_projects(self, session_id: str) -> int:
        return sum(1 for project in self.list(Project) if project.session_id == session_id)

    def count_active_audits(self, session_id: str) -> int:
        terminal = {"complete", "failed_partial", "failed", "waiting_for_user"}
        return sum(
            1
            for audit in self.list(Audit)
            if audit.session_id == session_id and audit.status.value not in terminal
        )

    def get_idempotent_result(self, scope: str, key: str) -> str | None:
        response = self.table.get_item(Key={"pk": f"IDEMP#{scope}", "sk": key})
        item = response.get("Item")
        return str(item["result_id"]) if item else None

    def record_idempotent_result(self, scope: str, key: str, result_id: str) -> None:
        try:
            self.table.put_item(
                Item={"pk": f"IDEMP#{scope}", "sk": key, "result_id": result_id},
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise

    def append_event(self, audit: Audit, event: AuditEvent) -> AuditEvent:
        # An interrupted writer can leave an event row ahead of the audit's
        # counter. Allocate a fresh sequence and retry that narrow collision
        # rather than crashing the polling worker and relying on redelivery.
        while True:
            counter = self.table.update_item(
                Key={"pk": "OBJECT#audit", "sk": audit.audit_id},
                UpdateExpression="ADD event_sequence :one",
                ExpressionAttributeValues={":one": 1},
                ReturnValues="UPDATED_NEW",
            )
            sequence = int(counter["Attributes"]["event_sequence"])
            committed = event.model_copy(update={"sequence": sequence})
            try:
                self.table.put_item(
                    Item={
                        "pk": f"EVENT#{audit.audit_id}",
                        "sk": f"{sequence:012d}",
                        "event_id": committed.event_id,
                        "payload": committed.model_dump_json(),
                    },
                    ConditionExpression="attribute_not_exists(pk)",
                )
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                    continue
                raise
            break
        current = self.get(Audit, audit.audit_id)
        if current is None:
            raise KeyError(audit.audit_id)
        current.last_event_sequence = sequence
        current.updated_at = utc_now()
        audit.last_event_sequence = sequence
        self.put(current)
        return committed

    def list_events(self, audit_id: str, after_sequence: int = 0) -> Sequence[AuditEvent]:
        items = self._all_query(
            KeyConditionExpression=Key("pk").eq(f"EVENT#{audit_id}")
            & Key("sk").gt(f"{after_sequence:012d}"),
            ConsistentRead=True,
        )
        return [AuditEvent.model_validate_json(item["payload"]) for item in items]

    def event_sequence(self, audit_id: str, event_id: str) -> int | None:
        return next(
            (event.sequence for event in self.list_events(audit_id) if event.event_id == event_id),
            None,
        )

    def acquire_audit_lease(self, audit_id: str, owner: str, lease_seconds: int) -> bool:
        now = int(utc_now().timestamp())
        try:
            self.table.update_item(
                Key={"pk": "OBJECT#audit", "sk": audit_id},
                UpdateExpression="SET lease_owner = :owner, lease_until_epoch = :until",
                ConditionExpression=(
                    "attribute_exists(pk) AND (attribute_not_exists(lease_until_epoch) "
                    "OR lease_until_epoch < :now OR lease_owner = :owner)"
                ),
                ExpressionAttributeValues={
                    ":owner": owner,
                    ":until": now + lease_seconds,
                    ":now": now,
                },
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise

    def release_audit_lease(self, audit_id: str, owner: str) -> None:
        try:
            self.table.update_item(
                Key={"pk": "OBJECT#audit", "sk": audit_id},
                UpdateExpression="REMOVE lease_owner, lease_until_epoch",
                ConditionExpression="lease_owner = :owner",
                ExpressionAttributeValues={":owner": owner},
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise

    def delete_project(self, project_id: str) -> None:
        artifacts = self.list(Artifact, project_id)
        audits = self.list(Audit, project_id)
        keys = [{"pk": "OBJECT#artifact", "sk": item.artifact_id} for item in artifacts]
        keys.append({"pk": "OBJECT#project", "sk": project_id})
        for audit in audits:
            child_items = self._all_query(
                IndexName="parent-index",
                KeyConditionExpression=Key("gsi1pk").eq(f"PARENT#{audit.audit_id}"),
            )
            events = self._all_query(KeyConditionExpression=Key("pk").eq(f"EVENT#{audit.audit_id}"))
            keys.extend({"pk": item["pk"], "sk": item["sk"]} for item in child_items + events)
            owned_ids = {
                "hypothesis": audit.hypothesis_ids,
                "evidence": audit.evidence_ids,
                "finding": audit.finding_ids,
                "correction": audit.correction_ids,
                "question": audit.question_ids,
            }
            for kind, object_ids in owned_ids.items():
                keys.extend({"pk": f"OBJECT#{kind}", "sk": object_id} for object_id in object_ids)
            keys.append({"pk": "OBJECT#audit", "sk": audit.audit_id})
        with self.table.batch_writer() as batch:
            for key in keys:
                batch.delete_item(Key=key)

    def seed(self, models: Iterable[BaseModel]) -> None:
        for model in models:
            self.put(model)
