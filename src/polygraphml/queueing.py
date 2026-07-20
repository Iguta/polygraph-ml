from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import boto3

from polygraphml.domain.models import JobMessage
from polygraphml.errors import PolygraphError
from polygraphml.storage.repository import SqliteRepository


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    receipt: int | str
    message: JobMessage
    attempts: int = 1


class AuditQueue(Protocol):
    def send(self, message: JobMessage) -> bool: ...

    def receive(self) -> ClaimedJob | None: ...

    def heartbeat(self, job: ClaimedJob) -> None: ...

    def acknowledge(self, job: ClaimedJob) -> None: ...

    def retry(self, job: ClaimedJob, error_code: str) -> str: ...


class LocalAuditQueue:
    def __init__(self, repository: SqliteRepository, lease_seconds: int) -> None:
        self.repository = repository
        self.lease_seconds = lease_seconds

    def send(self, message: JobMessage) -> bool:
        return self.repository.enqueue(message)

    def receive(self) -> ClaimedJob | None:
        claimed = self.repository.claim_job(self.lease_seconds)
        if claimed is None:
            return None
        receipt, message = claimed
        return ClaimedJob(receipt=receipt, message=message)

    def heartbeat(self, job: ClaimedJob) -> None:
        self.repository.extend_job(int(job.receipt), self.lease_seconds)

    def acknowledge(self, job: ClaimedJob) -> None:
        self.repository.acknowledge_job(int(job.receipt))

    def retry(self, job: ClaimedJob, error_code: str) -> str:
        return self.repository.fail_job(int(job.receipt), error_code)


class SqsAuditQueue:
    """Identifiers-only SQS adapter with explicit heartbeat and DLQ handoff."""

    def __init__(
        self,
        queue_url: str,
        dlq_url: str,
        visibility_timeout: int,
        *,
        region: str,
        client: Any | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.queue_url = queue_url
        self.dlq_url = dlq_url
        self.visibility_timeout = visibility_timeout
        self.max_attempts = max_attempts
        self.client = client or boto3.client("sqs", region_name=region)

    def send(self, message: JobMessage) -> bool:
        body = message.model_dump_json()
        self._assert_safe_payload(body)
        self.client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=body,
            MessageAttributes={
                "schema_version": {"DataType": "String", "StringValue": message.schema_version},
                "operation": {"DataType": "String", "StringValue": message.operation},
            },
        )
        return True

    def receive(self) -> ClaimedJob | None:
        response = self.client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=self.visibility_timeout,
            AttributeNames=["ApproximateReceiveCount"],
        )
        messages = response.get("Messages", [])
        if not messages:
            return None
        raw = messages[0]
        try:
            message = JobMessage.model_validate_json(raw["Body"])
            receipt = str(raw["ReceiptHandle"])
            attempts = int(raw.get("Attributes", {}).get("ApproximateReceiveCount", "1"))
        except (KeyError, TypeError, ValueError) as exc:
            raise PolygraphError("QUEUE_MESSAGE_INVALID", "SQS message failed validation.") from exc
        return ClaimedJob(receipt=receipt, message=message, attempts=attempts)

    def heartbeat(self, job: ClaimedJob) -> None:
        self.client.change_message_visibility(
            QueueUrl=self.queue_url,
            ReceiptHandle=str(job.receipt),
            VisibilityTimeout=self.visibility_timeout,
        )

    def acknowledge(self, job: ClaimedJob) -> None:
        self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=str(job.receipt))

    def retry(self, job: ClaimedJob, error_code: str) -> str:
        if job.attempts >= self.max_attempts:
            body = json.dumps(
                {
                    **job.message.model_dump(mode="json"),
                    "failure_code": error_code[:200],
                    "attempts": job.attempts,
                },
                separators=(",", ":"),
            )
            self._assert_safe_payload(body)
            self.client.send_message(QueueUrl=self.dlq_url, MessageBody=body)
            self.acknowledge(job)
            return "dead"
        self.client.change_message_visibility(
            QueueUrl=self.queue_url,
            ReceiptHandle=str(job.receipt),
            VisibilityTimeout=1,
        )
        return "queued"

    @staticmethod
    def _assert_safe_payload(body: str) -> None:
        normalized = body.lower()
        forbidden = ("openai_api_key", "authorization", "bearer ", "artifact_bytes", "prompt")
        if any(token in normalized for token in forbidden) or len(body.encode()) > 8192:
            raise PolygraphError(
                "QUEUE_PAYLOAD_UNSAFE", "Queue messages may contain identifiers only."
            )
