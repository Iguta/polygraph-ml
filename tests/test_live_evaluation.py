from __future__ import annotations

import pytest

from polygraphml.agent.runtime import (
    AgentInvestigationResult,
    AuditAgentContext,
    fixture_investigation,
)
from polygraphml.benchmarks.catalog import (
    HARD_NEGATIVE_BENCHMARK_ID,
    POST_OUTCOME_BENCHMARK_ID,
    TARGET_PROXY_BENCHMARK_ID,
)
from polygraphml.benchmarks.live_evaluate import (
    LIVE_CASES,
    run_live_evaluation,
    select_answer,
)
from polygraphml.domain.models import (
    AgentExecutionProvenance,
    FindingMechanism,
    Question,
)
from polygraphml.errors import PolygraphError


def question(options: list[str]) -> Question:
    return Question(
        question_id="qst_1",
        audit_id="aud_1",
        text="Which provenance statement is true?",
        why_it_matters="It changes the tested mechanism.",
        affected_hypothesis_ids=["hyp_1"],
        answer_type="single_choice",
        options=options,
        blocking=True,
    )


def test_live_gate_is_exactly_three_predeclared_cases() -> None:
    assert len(LIVE_CASES) == 3
    assert len({case[0] for case in LIVE_CASES}) == 3


def test_answer_selection_uses_semantics_without_rewriting_options() -> None:
    assert select_answer(question(["before", "after", "unknown"]), "after") == "after"
    assert select_answer(question(["Independent input", "Derived from target"]), "derived") == (
        "Derived from target"
    )
    assert select_answer(question(["Available before", "Depends"]), "before") == (
        "Available before"
    )
    assert select_answer(question(["Option A", "Option B"]), "before") == "Option A"


async def test_live_gate_runs_exactly_three_cases_with_sanitized_mocked_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def mocked_live_agent(
        _settings: object,
        context: AuditAgentContext,
        audit_id: str,
    ) -> AgentInvestigationResult:
        calls.append(audit_id)
        if "engagement_band" in context.candidate_features:
            feature = "engagement_band"
            mechanism = FindingMechanism.TARGET_PROXY
        elif "previous_call_duration" in context.candidate_features:
            feature = "previous_call_duration"
            mechanism = FindingMechanism.POST_OUTCOME
        elif "call_duration" in context.candidate_features:
            feature = "call_duration"
            mechanism = FindingMechanism.POST_OUTCOME
        else:
            feature = "duration"
            mechanism = FindingMechanism.POST_OUTCOME
        return AgentInvestigationResult(
            plan=fixture_investigation(feature, mechanism),
            execution=AgentExecutionProvenance(
                provider="openai",
                mode="live",
                requested_model="gpt-5.6-sol",
                resolved_model="gpt-5.6-sol",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                latency_ms=25,
                trace_id=f"trace-{len(calls)}",
            ),
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-a-real-secret")
    # Exercise the exact three-case orchestration without loading the full public
    # flagship a second time in the same pytest process. The production constant
    # is asserted independently above and `make benchmarks` owns the full-data gate.
    monkeypatch.setattr(
        "polygraphml.benchmarks.live_evaluate.LIVE_CASES",
        (
            (POST_OUTCOME_BENCHMARK_ID, "post_outcome", "call_duration", "after"),
            (TARGET_PROXY_BENCHMARK_ID, "target_proxy", "engagement_band", "derived"),
            (
                HARD_NEGATIVE_BENCHMARK_ID,
                "post_outcome",
                "previous_call_duration",
                "before",
            ),
        ),
    )
    monkeypatch.setattr("polygraphml.worker.coordinator.run_live_investigation", mocked_live_agent)
    result = await run_live_evaluation()

    assert len(calls) == 3
    assert result.case_count == 3
    assert result.passed is True
    assert result.total_tokens == 45
    assert result.payloads_included is False
    assert all(case.agent_mode == "live" and case.passed for case in result.cases)


async def test_live_gate_refuses_an_empty_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    with pytest.raises(PolygraphError, match="Set OPENAI_API_KEY"):
        await run_live_evaluation()
