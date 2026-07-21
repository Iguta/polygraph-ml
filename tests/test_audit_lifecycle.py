from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from polygraphml.api.container import AppContainer
from polygraphml.config import Settings
from polygraphml.domain.models import Audit, AuditStatus, EventType, Finding, utc_now
from polygraphml.errors import PolygraphError
from polygraphml.worker.coordinator import AuditCoordinator


async def test_worker_recovers_a_queued_audit_after_enqueue_failure(
    authorized_client: tuple[TestClient, AppContainer, Settings, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, container, settings, headers = authorized_client
    project = client.post(
        "/api/v1/projects/from-benchmark",
        headers=headers,
        json={"benchmark_id": "synthetic_campaign_leak_v1"},
    ).json()["data"]
    original_send = container.queue.send
    monkeypatch.setattr(
        container.queue, "send", lambda message: (_ for _ in ()).throw(RuntimeError())
    )
    response = client.post(
        "/api/v1/audits",
        headers={**headers, "Idempotency-Key": "audit-enqueue-recovery"},
        json={
            "project_id": project["project_id"],
            "scenario_revision": 1,
            "mode": "complete_audit",
        },
    )
    assert response.status_code == 202
    audit = container.repository.get(Audit, response.json()["data"]["audit_id"])
    assert audit and audit.checkpoint == "enqueue_pending"
    audit.updated_at = utc_now() - timedelta(seconds=settings.enqueue_recovery_seconds + 1)
    container.repository.put(audit)
    monkeypatch.setattr(container.queue, "send", original_send)
    coordinator = AuditCoordinator(
        settings, container.repository, container.artifacts, container.queue
    )
    assert coordinator.reconcile_queued_audits() == 1
    assert container.queue.receive() is not None


async def test_fixture_benchmark_question_resume_verdict_and_report(
    authorized_client: tuple[TestClient, AppContainer, Settings, dict[str, str]],
) -> None:
    client, container, settings, headers = authorized_client
    project_response = client.post(
        "/api/v1/projects/from-benchmark",
        headers=headers,
        json={"benchmark_id": "synthetic_campaign_leak_v1"},
    )
    assert project_response.status_code == 201
    project = project_response.json()["data"]
    assert project["status"] == "ready"
    assert {artifact["kind"] for artifact in project["artifacts"]} == {
        "dataset",
        "model",
        "notebook",
    }

    audit_response = client.post(
        "/api/v1/audits",
        headers={**headers, "Idempotency-Key": "audit-fixture-001"},
        json={
            "project_id": project["project_id"],
            "scenario_revision": 1,
            "mode": "complete_audit",
        },
    )
    assert audit_response.status_code == 202
    audit = audit_response.json()["data"]

    coordinator = AuditCoordinator(
        settings, container.repository, container.artifacts, container.queue
    )
    start_job = container.queue.receive()
    assert start_job is not None
    await coordinator.process(start_job)

    audit = client.get(f"/api/v1/audits/{audit['audit_id']}", headers=headers).json()["data"]
    assert audit["status"] == AuditStatus.WAITING_FOR_USER
    assert audit["reproduction_tier"] == "exact_supported"
    assert audit["metric_comparison"]["reproduction_status"] == "within_tolerance"
    assert audit["metric_comparison"]["reported"]["protocol_id"] == "reported_claim_unverified"
    assert audit["metric_comparison"]["reported"]["reproduction_tier"] == "reported_claim"
    assert audit["metric_comparison"]["reproduced"]["reproduction_tier"] == "exact_supported"
    assert audit["provenance"]["compute_execution"]["mode"] == "bounded_subprocess"
    assert audit["provenance"]["compute_execution"]["sandboxed"] is False
    assert audit["provenance"]["agent_execution"]["mode"] == "fixture"
    assert len(audit["open_questions"]) == 1
    question = audit["open_questions"][0]
    assert question["why_it_matters"]
    assert "after" in question["options"]

    answer_response = client.post(
        f"/api/v1/audits/{audit['audit_id']}/answers",
        headers={**headers, "Idempotency-Key": "answer-fixture-001"},
        json={"question_id": question["question_id"], "answer": "after"},
    )
    assert answer_response.status_code == 202
    resume_job = container.queue.receive()
    assert resume_job is not None
    await coordinator.process(resume_job)

    completed = client.get(f"/api/v1/audits/{audit['audit_id']}", headers=headers).json()["data"]
    assert completed["status"] == AuditStatus.COMPLETE
    assert completed["verdict"]["trust_state"] == "materially_inflated"
    assert completed["metric_comparison"]["corrected"]["value"] < 0.95
    findings = {(item["mechanism"], item["status"]) for item in completed["findings"]}
    assert ("post_outcome", "confirmed") in findings
    assert ("group_contamination", "confirmed") in findings
    assert ("split_contamination", "cleared") in findings
    assert ("preprocessing", "cleared") in findings

    events_response = client.get(
        f"/api/v1/audits/{audit['audit_id']}/events",
        headers={**headers, "Accept": "application/json"},
        params={"after_sequence": 0},
    )
    events = events_response.json()["data"]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert any(event["type"] == EventType.REASONING_SUMMARY for event in events)
    assert any(
        event["type"] == EventType.WARNING and event["payload"]["code"] == "SEMANTIC_DEGRADED"
        for event in events
    )
    assert all("chain_of_thought" not in str(event["payload"]).lower() for event in events)

    replay = client.get(
        f"/api/v1/audits/{audit['audit_id']}/events",
        headers={**headers, "Accept": "application/json"},
        params={"after_sequence": events[-2]["sequence"]},
    ).json()["data"]
    assert [event["event_id"] for event in replay] == [events[-1]["event_id"]]

    header_replay = client.get(
        f"/api/v1/audits/{audit['audit_id']}/events",
        headers={
            **headers,
            "Accept": "application/json",
            "Last-Event-ID": events[-2]["event_id"],
        },
    ).json()["data"]
    assert [event["event_id"] for event in header_replay] == [events[-1]["event_id"]]

    report_response = client.post(
        f"/api/v1/audits/{audit['audit_id']}/report",
        headers=headers,
        json={"audience": "technical"},
    )
    assert report_response.status_code == 200
    report = report_response.json()["data"]
    assert "Reported, reproduced, and corrected performance" in report["content"]
    assert "Deterministic compute provenance" in report["content"]
    executive = client.post(
        f"/api/v1/audits/{audit['audit_id']}/report",
        headers=headers,
        json={"audience": "executive"},
    ).json()["data"]
    assert "Executive decision brief" in executive["content"]
    assert "Business impact" in executive["content"]
    assert "Package versions" not in executive["content"]
    assert executive["content"] != report["content"]

    repair_response = client.post(
        f"/api/v1/audits/{audit['audit_id']}/repair-bundle", headers=headers
    )
    assert repair_response.status_code == 200
    repair = repair_response.json()["data"]
    assert repair["status"] == "available"
    assert repair["download_url"].startswith("/api/v1/audits/")
    downloaded = client.get(repair["download_url"], headers=headers)
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == repair["sha256"]
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        assert set(archive.namelist()) == {
            "README.md",
            "correction.json",
            "feature-list.patch",
            "protocol.json",
        }
        patch = archive.read("feature-list.patch").decode()
        assert "-features =" in patch
        assert "call_duration" in patch
    assert "call_duration" in report["content"]

    with client.stream(
        "GET",
        f"/api/v1/audits/{audit['audit_id']}/events",
        headers={**headers, "Accept": "text/event-stream"},
        params={"after_sequence": events[-2]["sequence"]},
    ) as stream:
        body = "".join(stream.iter_text())
    assert "event: audit_state" in body
    assert events[-1]["event_id"] in body

    owned_finding_ids = [finding["finding_id"] for finding in completed["findings"]]
    assert (
        client.delete(f"/api/v1/projects/{project['project_id']}", headers=headers).status_code
        == 204
    )
    assert all(
        container.repository.get(Finding, finding_id) is None for finding_id in owned_finding_ids
    )


async def test_start_and_answer_are_idempotent(
    authorized_client: tuple[TestClient, AppContainer, Settings, dict[str, str]],
) -> None:
    client, container, settings, headers = authorized_client
    project = client.post(
        "/api/v1/projects/from-benchmark",
        headers=headers,
        json={"benchmark_id": "synthetic_campaign_leak_v1"},
    ).json()["data"]
    request = {
        "project_id": project["project_id"],
        "scenario_revision": 1,
        "mode": "complete_audit",
    }
    request_headers = {**headers, "Idempotency-Key": "same-start-key"}
    first = client.post("/api/v1/audits", headers=request_headers, json=request).json()["data"]
    second = client.post("/api/v1/audits", headers=request_headers, json=request).json()["data"]
    assert first["audit_id"] == second["audit_id"]
    assert len(container.repository.job_rows(first["audit_id"])) == 1

    coordinator = AuditCoordinator(
        settings, container.repository, container.artifacts, container.queue
    )
    start_job = container.queue.receive()
    assert start_job is not None
    await coordinator.process(start_job)
    waiting = client.get(f"/api/v1/audits/{first['audit_id']}", headers=headers).json()["data"]
    question = waiting["open_questions"][0]
    answer_headers = {**headers, "Idempotency-Key": "same-answer-key"}
    answer = {"question_id": question["question_id"], "answer": "after"}
    client.post(f"/api/v1/audits/{first['audit_id']}/answers", headers=answer_headers, json=answer)
    client.post(f"/api/v1/audits/{first['audit_id']}/answers", headers=answer_headers, json=answer)
    jobs = container.repository.job_rows(first["audit_id"])
    assert len(jobs) == 2
    assert [row["status"] for row in jobs] == ["complete", "queued"]


async def test_retryable_worker_error_returns_audit_to_queue(
    authorized_client: tuple[TestClient, AppContainer, Settings, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, container, settings, headers = authorized_client
    project = client.post(
        "/api/v1/projects/from-benchmark",
        headers=headers,
        json={"benchmark_id": "synthetic_campaign_leak_v1"},
    ).json()["data"]
    audit = client.post(
        "/api/v1/audits",
        headers={**headers, "Idempotency-Key": "retryable-worker-error"},
        json={
            "project_id": project["project_id"],
            "scenario_revision": 1,
            "mode": "complete_audit",
        },
    ).json()["data"]
    coordinator = AuditCoordinator(
        settings, container.repository, container.artifacts, container.queue
    )
    job = container.queue.receive()
    assert job is not None

    async def fail_once(_: object) -> None:
        raise RuntimeError("transient worker failure")

    monkeypatch.setattr(coordinator, "_start", fail_once)
    await coordinator.process(job)
    retried = client.get(f"/api/v1/audits/{audit['audit_id']}", headers=headers).json()["data"]
    assert retried["status"] == "queued"
    assert container.repository.job_rows(audit["audit_id"])[0]["status"] == "queued"


async def test_compute_timeout_is_visible_inconclusive_and_not_retried(
    authorized_client: tuple[TestClient, AppContainer, Settings, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, container, settings, headers = authorized_client
    project = client.post(
        "/api/v1/projects/from-benchmark",
        headers=headers,
        json={"benchmark_id": "synthetic_campaign_leak_v1"},
    ).json()["data"]
    audit = client.post(
        "/api/v1/audits",
        headers={**headers, "Idempotency-Key": "bounded-timeout"},
        json={
            "project_id": project["project_id"],
            "scenario_revision": 1,
            "mode": "complete_audit",
        },
    ).json()["data"]
    coordinator = AuditCoordinator(
        settings, container.repository, container.artifacts, container.queue
    )
    job = container.queue.receive()
    assert job is not None

    async def time_out(_: object) -> None:
        raise PolygraphError("EXECUTION_TIMEOUT", "Bounded evaluation timed out.")

    monkeypatch.setattr(coordinator, "_start", time_out)
    await coordinator.process(job)

    completed = client.get(f"/api/v1/audits/{audit['audit_id']}", headers=headers).json()["data"]
    assert completed["status"] == "failed_partial"
    assert completed["checkpoint"] == "compute_inconclusive"
    assert completed["verdict"]["trust_state"] == "inconclusive"
    assert completed["findings"][0]["status"] == "inconclusive"
    assert container.repository.job_rows(audit["audit_id"])[0]["status"] == "complete"


async def test_public_uci_covid_model_data_and_notebook_clean_control(
    authorized_client: tuple[TestClient, AppContainer, Settings, dict[str, str]],
) -> None:
    client, container, settings, headers = authorized_client
    benchmark = next(
        item
        for item in client.get("/api/v1/benchmarks", headers=headers).json()["data"]
        if item["benchmark_id"] == "uci_covid_surveillance_clean_v1"
    )
    assert benchmark["license_name"] == "CC BY 4.0"
    assert benchmark["source_url"].startswith("https://archive.ics.uci.edu/")
    assert benchmark["expectations"] == [
        {
            "mechanism": "post_outcome",
            "feature": "A07",
            "expected_status": "cleared",
        }
    ]
    assert benchmark["artifact_hashes"]["source_csv_sha256"]

    project = client.post(
        "/api/v1/projects/from-benchmark",
        headers=headers,
        json={"benchmark_id": benchmark["benchmark_id"]},
    ).json()["data"]
    assert {artifact["kind"] for artifact in project["artifacts"]} == {
        "dataset",
        "model",
        "notebook",
    }
    started = client.post(
        "/api/v1/audits",
        headers={**headers, "Idempotency-Key": "uci-covid-clean-start"},
        json={
            "project_id": project["project_id"],
            "scenario_revision": 1,
            "mode": "complete_audit",
        },
    ).json()["data"]
    coordinator = AuditCoordinator(
        settings, container.repository, container.artifacts, container.queue
    )
    job = container.queue.receive()
    assert job is not None
    await coordinator.process(job)
    waiting = client.get(f"/api/v1/audits/{started['audit_id']}", headers=headers).json()["data"]
    assert waiting["status"] == "waiting_for_user"
    assert "A07" in waiting["open_questions"][0]["text"]

    client.post(
        f"/api/v1/audits/{started['audit_id']}/answers",
        headers={**headers, "Idempotency-Key": "uci-covid-clean-answer"},
        json={
            "question_id": waiting["open_questions"][0]["question_id"],
            "answer": "before",
        },
    )
    resume = container.queue.receive()
    assert resume is not None
    await coordinator.process(resume)
    completed = client.get(f"/api/v1/audits/{started['audit_id']}", headers=headers).json()["data"]
    assert completed["status"] == "complete"
    assert completed["metric_comparison"]["reproduction_status"] == "within_tolerance"
    assert not any(finding["status"] == "confirmed" for finding in completed["findings"])
    assert completed["provenance"]["artifact_hashes"]
