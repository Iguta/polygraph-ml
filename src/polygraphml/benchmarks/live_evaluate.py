from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polygraphml.api.container import build_container
from polygraphml.benchmarks.catalog import (
    HARD_NEGATIVE_BENCHMARK_ID,
    TARGET_PROXY_BENCHMARK_ID,
    UCI_BANK_BENCHMARK_ID,
)
from polygraphml.config import Settings
from polygraphml.domain.models import (
    Actor,
    Audit,
    AuditMode,
    AuditStatus,
    EventType,
    Finding,
    FindingStatus,
    Hypothesis,
    Question,
)
from polygraphml.errors import PolygraphError
from polygraphml.worker.coordinator import AuditCoordinator


class LiveCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_id: str
    expected_mechanism: str
    expected_feature: str
    selected_mechanism: str | None
    selected_feature: str | None
    question_material: bool
    observed_confirmed: list[str]
    observed_cleared: list[str]
    passed: bool
    agent_mode: Literal["live", "fixture", "degraded"]
    requested_model: str
    resolved_model: str | None
    reasoning_effort: str
    harness_version: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    trace_id: str | None
    response_id: str | None
    request_id: str | None
    tool_result_event_count: int
    final_status: str
    failure_code: str | None = None


class LiveEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    created_at: datetime
    mode: Literal["live"] = "live"
    case_count: Literal[3] = 3
    model: str
    passed: bool
    cases: list[LiveCaseResult] = Field(min_length=3, max_length=3)
    total_tokens: int
    total_agent_latency_ms: int
    estimated_openai_cost_usd: None = None
    cost_note: str = "Cost is not estimated locally; use the provider usage record."
    payloads_included: Literal[False] = False
    raw_chain_of_thought_stored: Literal[False] = False
    trace_include_sensitive_data: Literal[False] = False


LIVE_CASES = (
    (UCI_BANK_BENCHMARK_ID, "post_outcome", "duration", "after"),
    (TARGET_PROXY_BENCHMARK_ID, "target_proxy", "engagement_band", "derived"),
    (
        HARD_NEGATIVE_BENCHMARK_ID,
        "post_outcome",
        "previous_call_duration",
        "before",
    ),
)


def ensure_fresh_output(output: Path) -> None:
    if output.exists():
        raise PolygraphError(
            "LIVE_EVALUATION_EXISTS",
            f"Refusing to overwrite the existing live evaluation record: {output}",
            status_code=409,
        )


def select_answer(question: Question, intent: str) -> str:
    intent_tokens = {
        "after": ("after", "not_available"),
        "before": ("before", "available_at", "available before"),
        "derived": ("derived", "assigned_after", "target", "outcome"),
    }[intent]
    for option in question.options:
        normalized = option.strip().lower().replace(" ", "_")
        if any(token.replace(" ", "_") in normalized for token in intent_tokens):
            return option
    if question.options:
        return question.options[0]
    return {
        "after": "The feature is available only after the decision.",
        "before": "The feature is available before the decision.",
        "derived": "The feature is derived from the target outcome.",
    }[intent]


async def run_live_evaluation() -> LiveEvaluationResult:
    with tempfile.TemporaryDirectory(prefix="polygraphml-live-eval-") as temporary:
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
                "Set OPENAI_API_KEY in the ignored .env before running the three-case live gate.",
                status_code=503,
            )
        container = build_container(settings)
        coordinator = AuditCoordinator(
            settings, container.repository, container.artifacts, container.queue
        )
        case_results: list[LiveCaseResult] = []
        for index, (benchmark_id, mechanism, feature, answer_intent) in enumerate(LIVE_CASES):
            session, _ = container.repository.create_session(3600)
            project = container.projects.create_benchmark_project(session, benchmark_id)
            audit = container.audits.start(
                session,
                project,
                1,
                AuditMode.COMPLETE,
                f"live-eval-start-{index}",
            )
            start_job = container.queue.receive()
            if start_job is None:
                raise RuntimeError("Live evaluation start job was not queued.")
            await coordinator.process(start_job)
            waiting = container.repository.get(Audit, audit.audit_id)
            if waiting is None or not waiting.question_ids:
                raise RuntimeError("Live evaluation did not persist its checkpoint question.")
            question = container.repository.get(Question, waiting.question_ids[-1])
            if question is None:
                raise RuntimeError("Live evaluation question was not persisted.")
            hypothesis = container.repository.get(Hypothesis, question.affected_hypothesis_ids[0])
            container.audits.answer(
                session,
                waiting,
                question,
                select_answer(question, answer_intent),
                f"live-eval-answer-{index}",
            )
            resume_job = container.queue.receive()
            if resume_job is None:
                raise RuntimeError("Live evaluation resume job was not queued.")
            await coordinator.process(resume_job)
            completed = container.repository.get(Audit, audit.audit_id)
            if completed is None:
                raise RuntimeError("Live evaluation audit disappeared before completion.")
            findings = [
                finding
                for finding_id in completed.finding_ids
                if (finding := container.repository.get(Finding, finding_id)) is not None
            ]
            selected_mechanism = hypothesis.mechanism.value if hypothesis else None
            selected_feature = (
                hypothesis.features[0] if hypothesis and hypothesis.features else None
            )
            confirmed_pairs = sorted(
                f"{finding.mechanism.value}:{finding.features[0]}"
                for finding in findings
                if finding.status == FindingStatus.CONFIRMED and finding.features
            )
            cleared_pairs = sorted(
                f"{finding.mechanism.value}:{finding.features[0]}"
                for finding in findings
                if finding.status == FindingStatus.CLEARED and finding.features
            )
            expected_pair = f"{mechanism}:{feature}"
            is_negative = benchmark_id == HARD_NEGATIVE_BENCHMARK_ID
            execution = completed.provenance.agent_execution
            if execution is None:
                raise RuntimeError("Live evaluation did not record agent provenance.")
            events = container.repository.list_events(audit.audit_id)
            passed = (
                completed.status == AuditStatus.COMPLETE
                and execution.mode == "live"
                and selected_mechanism == mechanism
                and selected_feature == feature
                and (
                    expected_pair in cleared_pairs
                    if is_negative
                    else expected_pair in confirmed_pairs
                )
                and (not confirmed_pairs if is_negative else True)
            )
            case_results.append(
                LiveCaseResult(
                    benchmark_id=benchmark_id,
                    expected_mechanism=mechanism,
                    expected_feature=feature,
                    selected_mechanism=selected_mechanism,
                    selected_feature=selected_feature,
                    question_material=(
                        selected_mechanism == mechanism and selected_feature == feature
                    ),
                    observed_confirmed=confirmed_pairs,
                    observed_cleared=cleared_pairs,
                    passed=passed,
                    agent_mode=execution.mode,
                    requested_model=execution.requested_model,
                    resolved_model=execution.resolved_model,
                    reasoning_effort=execution.reasoning_effort,
                    harness_version=execution.harness_version,
                    input_tokens=execution.input_tokens,
                    output_tokens=execution.output_tokens,
                    total_tokens=execution.total_tokens,
                    latency_ms=execution.latency_ms,
                    trace_id=execution.trace_id,
                    response_id=execution.response_id,
                    request_id=execution.request_id,
                    tool_result_event_count=sum(
                        event.type == EventType.TOOL_RESULT and event.actor == Actor.TOOL
                        for event in events
                    ),
                    final_status=completed.status.value,
                    failure_code=execution.failure_code,
                )
            )
        container.repository.close()
    return LiveEvaluationResult(
        created_at=datetime.now(UTC),
        model=settings.openai_model,
        passed=all(case.passed for case in case_results),
        cases=case_results,
        total_tokens=sum(case.total_tokens for case in case_results),
        total_agent_latency_ms=sum(case.latency_ms for case in case_results),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run exactly three authorized live GPT-5.6 evaluation cases."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results/live-evaluation-rerun.json"),
    )
    arguments = parser.parse_args()
    try:
        ensure_fresh_output(arguments.output)
        result = asyncio.run(run_live_evaluation())
    except PolygraphError as exc:
        raise SystemExit(f"{exc.code}: {exc}") from exc
    rendered = json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")
    print(f"Sanitized three-case live evaluation written to {arguments.output}")
    if not result.passed:
        raise SystemExit("Live evaluation completed but did not pass every declared case.")


if __name__ == "__main__":
    main()
