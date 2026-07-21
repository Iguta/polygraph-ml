from __future__ import annotations

from pathlib import Path

import boto3
from moto import mock_aws

from polygraphml.domain.models import (
    Actor,
    AdapterStatus,
    Artifact,
    ArtifactKind,
    Audit,
    AuditEvent,
    AuditMode,
    AuditStatus,
    EventType,
    Project,
    ProjectSource,
    ProjectStatus,
    Question,
    SourceType,
)
from polygraphml.storage.artifacts import S3ArtifactStore
from polygraphml.storage.dynamodb import DynamoRepository


def create_state_table(resource: object) -> None:
    resource.create_table(  # type: ignore[attr-defined]
        TableName="polygraphml-test",
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": name, "AttributeType": "S"}
            for name in ("pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk")
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "parent-index",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "token-index",
                "KeySchema": [
                    {"AttributeName": "gsi2pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi2sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )


@mock_aws
def test_dynamo_repository_shared_state_events_leases_and_deletion() -> None:
    resource = boto3.resource("dynamodb", region_name="us-east-1")
    create_state_table(resource)
    repository = DynamoRepository("polygraphml-test", "us-east-1", resource=resource)

    session, token = repository.create_session(300)
    assert repository.get_session_by_token(token) == session
    assert repository.get_session_by_token("invalid") is None

    project = repository.put(
        Project(
            project_id="prj_1",
            session_id=session.session_id,
            name="AWS audit",
            source=ProjectSource(type=SourceType.UPLOAD),
            status=ProjectStatus.READY,
        )
    )
    for number in (1, 2):
        repository.put(
            Artifact(
                artifact_id=f"art_{number}",
                project_id=project.project_id,
                kind=ArtifactKind.DATASET,
                filename=f"data-{number}.csv",
                sha256=str(number) * 64,
                size_bytes=10,
                media_type="text/csv",
                storage_key=f"prj_1/{number}/data.csv",
                adapter="csv",
                adapter_status=AdapterStatus.SUPPORTED,
            )
        )
    assert repository.count_projects(session.session_id) == 1
    assert len(repository.list(Artifact, project.project_id)) == 2

    audit = repository.put(
        Audit(
            audit_id="aud_1",
            project_id=project.project_id,
            session_id=session.session_id,
            scenario_revision=1,
            mode=AuditMode.COMPLETE,
            status=AuditStatus.QUEUED,
        )
    )
    repository.put(
        Question(
            question_id="qst_1",
            audit_id=audit.audit_id,
            text="When is the feature available?",
            why_it_matters="Timing determines availability.",
            affected_hypothesis_ids=["hyp_1"],
            answer_type="single_choice",
            options=["before", "after"],
            blocking=True,
        )
    )
    assert repository.count_active_audits(session.session_id) == 1
    assert repository.get(Audit, audit.audit_id) == audit

    repository.record_idempotent_result("audit:start", "key-123456", audit.audit_id)
    repository.record_idempotent_result("audit:start", "key-123456", "aud_other")
    assert repository.get_idempotent_result("audit:start", "key-123456") == audit.audit_id

    for number in (1, 2):
        committed = repository.append_event(
            audit,
            AuditEvent(
                event_id=f"evt_{number}",
                audit_id=audit.audit_id,
                sequence=1,
                type=EventType.AUDIT_STATE,
                actor=Actor.SYSTEM,
                payload={"number": number},
            ),
        )
        assert committed.sequence == number
    assert [event.sequence for event in repository.list_events(audit.audit_id, 1)] == [2]
    assert repository.event_sequence(audit.audit_id, "evt_2") == 2
    assert repository.event_sequence(audit.audit_id, "missing") is None

    stale_audit = audit.model_copy(update={"last_event_sequence": 0})
    repository.put(stale_audit)
    third = repository.append_event(
        stale_audit,
        AuditEvent(
            event_id="evt_3",
            audit_id=audit.audit_id,
            sequence=1,
            type=EventType.AUDIT_STATE,
            actor=Actor.SYSTEM,
            payload={"number": 3},
        ),
    )
    assert third.sequence == 3

    # Simulate a crash after an event row was committed but before its counter
    # update became durable. The next append must allocate a new sequence.
    resource.Table("polygraphml-test").put_item(
        Item={
            "pk": "EVENT#aud_1",
            "sk": "000000000004",
            "event_id": "evt_orphaned",
            "payload": AuditEvent(
                event_id="evt_orphaned",
                audit_id=audit.audit_id,
                sequence=4,
                type=EventType.WARNING,
                actor=Actor.SYSTEM,
                payload={"simulated": "interrupted_writer"},
            ).model_dump_json(),
        }
    )
    resource.Table("polygraphml-test").update_item(
        Key={"pk": "OBJECT#audit", "sk": audit.audit_id},
        UpdateExpression="SET event_sequence = :sequence",
        ExpressionAttributeValues={":sequence": 3},
    )
    recovered = repository.append_event(
        audit,
        AuditEvent(
            event_id="evt_5",
            audit_id=audit.audit_id,
            sequence=1,
            type=EventType.AUDIT_STATE,
            actor=Actor.SYSTEM,
            payload={"number": 5},
        ),
    )
    assert recovered.sequence == 5

    assert repository.acquire_audit_lease(audit.audit_id, "worker-a", 120) is True
    leased_audit = repository.get(Audit, audit.audit_id)
    assert leased_audit is not None
    leased_audit.checkpoint = "lease-preservation"
    repository.put(leased_audit)
    assert repository.acquire_audit_lease(audit.audit_id, "worker-b", 120) is False
    repository.release_audit_lease(audit.audit_id, "worker-b")
    repository.release_audit_lease(audit.audit_id, "worker-a")
    assert repository.acquire_audit_lease(audit.audit_id, "worker-b", 120) is True
    repository.release_audit_lease(audit.audit_id, "worker-b")

    repository.delete_project(project.project_id)
    assert repository.get(Project, project.project_id) is None
    assert repository.get(Audit, audit.audit_id) is None
    assert repository.list_events(audit.audit_id) == []
    repository.close()


@mock_aws
def test_s3_store_presign_checksum_download_and_retention_delete(tmp_path: Path) -> None:
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="polygraphml-artifacts")
    store = S3ArtifactStore("polygraphml-artifacts", "us-east-1", tmp_path / "cache", client=client)
    content = b"feature,target\n1,0\n2,1\n"
    key = store.key("prj_1", "dataset", "evidence.csv")
    size, digest = store.write(key, content, 1024)
    assert size == len(content)
    verified_path = store.verify(key, size, digest)
    assert verified_path == (store.root / key).resolve()

    cached = store.root / key
    cached.unlink()
    assert store.path_for_key(key).read_bytes() == content

    upload_url, headers = store.presign_put(key, "text/csv", digest)
    assert upload_url.startswith("https://")
    assert headers["x-amz-meta-sha256"] == digest
    assert headers["x-amz-server-side-encryption"] == "AES256"
    assert store.presign_get(key).startswith("https://")

    store.delete_project("prj_1")
    assert client.list_objects_v2(Bucket="polygraphml-artifacts").get("KeyCount") == 0
    assert not (store.root / "prj_1").exists()
