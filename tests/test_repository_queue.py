from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polygraphml.domain.models import (
    AdapterStatus,
    Artifact,
    ArtifactKind,
    Audit,
    AuditMode,
    AuditStatus,
    JobMessage,
    Project,
    ProjectSource,
    ProjectStatus,
    SourceType,
)
from polygraphml.errors import PolygraphError
from polygraphml.queueing import ClaimedJob, LocalAuditQueue, SqsAuditQueue
from polygraphml.storage.repository import SqliteRepository


def test_child_objects_do_not_overwrite_each_other(tmp_path: Path) -> None:
    repository = SqliteRepository(tmp_path / "db.sqlite")
    project = Project(
        project_id="prj_1",
        session_id="ses_1",
        name="Test",
        source=ProjectSource(type=SourceType.UPLOAD),
        status=ProjectStatus.READY_FOR_UPLOAD,
    )
    repository.put(project)
    for number in (1, 2):
        repository.put(
            Artifact(
                artifact_id=f"art_{number}",
                project_id=project.project_id,
                kind=ArtifactKind.DATASET,
                filename=f"data{number}.csv",
                sha256=str(number) * 64,
                size_bytes=1,
                media_type="text/csv",
                storage_key=f"prj_1/{number}/data.csv",
                adapter="csv",
                adapter_status=AdapterStatus.SUPPORTED,
            )
        )
    assert [artifact.artifact_id for artifact in repository.list(Artifact, "prj_1")] == [
        "art_1",
        "art_2",
    ]
    repository.close()


def test_queue_deduplicates_and_dead_letters_after_three_attempts(tmp_path: Path) -> None:
    repository = SqliteRepository(tmp_path / "db.sqlite")
    audit = Audit(
        audit_id="aud_1",
        project_id="prj_1",
        session_id="ses_1",
        scenario_revision=1,
        mode=AuditMode.COMPLETE,
        status=AuditStatus.QUEUED,
    )
    repository.put(audit)
    queue = LocalAuditQueue(repository, lease_seconds=1)
    message = JobMessage(
        audit_id=audit.audit_id,
        operation="start",
        idempotency_key="start:aud_1",
    )
    assert queue.send(message) is True
    assert queue.send(message) is False
    for attempt in range(3):
        claimed = queue.receive()
        assert claimed is not None
        status = queue.retry(claimed, "TEST_FAILURE")
        if attempt < 2:
            assert status == "queued"
            repository._connection.execute(
                "UPDATE jobs SET available_at = '1970-01-01T00:00:00+00:00'"
            )
        else:
            assert status == "dead"
    assert repository.job_rows()[0]["last_error"] == "TEST_FAILURE"
    repository.close()


class FakeSqs:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.messages: list[dict[str, Any]] = []

    def send_message(self, **kwargs: Any) -> dict[str, str]:
        self.calls.append(("send", kwargs))
        return {"MessageId": "message-1"}

    def receive_message(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("receive", kwargs))
        return {"Messages": self.messages}

    def change_message_visibility(self, **kwargs: Any) -> None:
        self.calls.append(("visibility", kwargs))

    def delete_message(self, **kwargs: Any) -> None:
        self.calls.append(("delete", kwargs))


def test_sqs_message_contract_contains_identifiers_only_and_moves_to_dlq() -> None:
    client = FakeSqs()
    queue = SqsAuditQueue(
        "https://sqs.example/audit",
        "https://sqs.example/dlq",
        300,
        region="us-east-1",
        client=client,
    )
    message = JobMessage(
        audit_id="aud_1",
        operation="resume",
        idempotency_key="resume:qst_1",
    )
    assert queue.send(message) is True
    sent = client.calls[0][1]["MessageBody"]
    assert set(JobMessage.model_validate_json(sent).model_dump()) == {
        "audit_id",
        "operation",
        "schema_version",
        "idempotency_key",
    }
    assert "openai" not in sent.lower()

    client.messages = [
        {
            "Body": message.model_dump_json(),
            "ReceiptHandle": "receipt-1",
            "Attributes": {"ApproximateReceiveCount": "3"},
        }
    ]
    claimed = queue.receive()
    assert claimed == ClaimedJob(receipt="receipt-1", message=message, attempts=3)
    assert queue.retry(claimed, "PROBE_TIMEOUT") == "dead"
    assert any(
        operation == "send" and call["QueueUrl"] == "https://sqs.example/dlq"
        for operation, call in client.calls
    )
    assert any(operation == "delete" for operation, _ in client.calls)


def test_sqs_payload_guard_rejects_secret_shaped_content() -> None:
    with pytest.raises(PolygraphError, match="identifiers only"):
        SqsAuditQueue._assert_safe_payload('{"authorization":"Bearer secret"}')
