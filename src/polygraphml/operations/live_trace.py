from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from polygraphml.api.container import build_container
from polygraphml.benchmarks.catalog import SYNTHETIC_BENCHMARK_ID
from polygraphml.config import Settings
from polygraphml.domain.models import (
    Actor,
    Audit,
    AuditEvent,
    AuditMode,
    AuditStatus,
    EventType,
    Finding,
    FindingStatus,
    Question,
)
from polygraphml.errors import PolygraphError
from polygraphml.worker.coordinator import AuditCoordinator


class SanitizedLiveTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    created_at: datetime
    mode: Literal["live"] = "live"
    model: str
    audit_id: str
    final_status: str
    event_count: int
    event_type_counts: dict[str, int]
    actor_counts: dict[str, int]
    last_event_sequence: int
    reproduction_tier: str | None
    confirmed_mechanisms: list[str]
    raw_chain_of_thought_stored: Literal[False] = False
    trace_include_sensitive_data: Literal[False] = False
    payloads_included: Literal[False] = False


def build_sanitized_live_trace(
    audit: Audit,
    events: Sequence[AuditEvent],
    findings: Sequence[Finding],
    model: str,
) -> SanitizedLiveTrace:
    return SanitizedLiveTrace(
        created_at=datetime.now(UTC),
        model=model,
        audit_id=audit.audit_id,
        final_status=audit.status.value,
        event_count=len(events),
        event_type_counts=dict(Counter(event.type.value for event in events)),
        actor_counts=dict(Counter(event.actor.value for event in events)),
        last_event_sequence=audit.last_event_sequence,
        reproduction_tier=(audit.reproduction_tier.value if audit.reproduction_tier else None),
        confirmed_mechanisms=sorted(
            finding.mechanism.value
            for finding in findings
            if finding.status == FindingStatus.CONFIRMED
        ),
    )


async def run_live_smoke() -> SanitizedLiveTrace:
    with tempfile.TemporaryDirectory(prefix="polygraphml-live-smoke-") as temporary:
        root = Path(temporary)
        settings = Settings(
            environment="test",
            agent_mode="live",
            database_path=root / "state.db",
            artifact_root=root / "artifacts",
            worker_lease_seconds=300,
        )
        if not settings.live_agent_ready:
            raise PolygraphError(
                "OPENAI_NOT_CONFIGURED",
                "Set OPENAI_API_KEY in the ignored .env before running the live smoke test.",
                status_code=503,
            )
        container = build_container(settings)
        coordinator = AuditCoordinator(
            settings, container.repository, container.artifacts, container.queue
        )
        session, _ = container.repository.create_session(3600)
        project = container.projects.create_benchmark_project(session, SYNTHETIC_BENCHMARK_ID)
        audit = container.audits.start(
            session,
            project,
            1,
            AuditMode.COMPLETE,
            "live-smoke-start",
        )
        start_job = container.queue.receive()
        if start_job is None:
            raise RuntimeError("Live smoke start job was not queued.")
        await coordinator.process(start_job)
        waiting = container.repository.get(Audit, audit.audit_id)
        if waiting is None or waiting.status != AuditStatus.WAITING_FOR_USER:
            raise RuntimeError("Live smoke did not reach the human checkpoint.")
        events = container.repository.list_events(audit.audit_id)
        if not any(event.actor == Actor.AGENT for event in events):
            raise RuntimeError("Live smoke degraded to fixture mode; no agent event was recorded.")
        if any(
            event.type == EventType.WARNING and event.payload.get("code") == "SEMANTIC_DEGRADED"
            for event in events
        ):
            raise RuntimeError("Live smoke emitted the semantic degradation warning.")
        question = container.repository.get(Question, waiting.question_ids[-1])
        if question is None:
            raise RuntimeError("Live smoke question was not persisted.")
        answer = (
            "after"
            if "after" in question.options
            else question.options[0]
            if question.options
            else "The feature is not available until after the decision."
        )
        container.audits.answer(
            session,
            waiting,
            question,
            answer,
            "live-smoke-answer",
        )
        resume_job = container.queue.receive()
        if resume_job is None:
            raise RuntimeError("Live smoke resume job was not queued.")
        await coordinator.process(resume_job)
        completed = container.repository.get(Audit, audit.audit_id)
        if completed is None or completed.status != AuditStatus.COMPLETE:
            raise RuntimeError("Live smoke audit did not complete.")
        all_events = container.repository.list_events(audit.audit_id)
        findings = [
            finding
            for finding_id in completed.finding_ids
            if (finding := container.repository.get(Finding, finding_id)) is not None
        ]
        trace = build_sanitized_live_trace(completed, all_events, findings, settings.openai_model)
        container.repository.close()
        return trace


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one real GPT-5.6 audit and save metadata-only trace evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/live-trace.json"),
    )
    arguments = parser.parse_args()
    try:
        trace = asyncio.run(run_live_smoke())
    except PolygraphError as exc:
        raise SystemExit(f"{exc.code}: {exc}") from exc
    rendered = json.dumps(trace.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")
    print(f"Sanitized live trace written to {arguments.output}")


if __name__ == "__main__":
    main()
