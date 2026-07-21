from __future__ import annotations

import json
import time
from dataclasses import dataclass

from agents import (
    Agent,
    ModelSettings,
    RunConfig,
    RunContextWrapper,
    Runner,
    function_tool,
    gen_trace_id,
    set_default_openai_key,
)
from openai.types.shared import Reasoning
from pydantic import BaseModel, ConfigDict, Field

from polygraphml.config import Settings
from polygraphml.domain.models import (
    AgentExecutionProvenance,
    DatasetProfile,
    FindingMechanism,
    ProbeKind,
    Scenario,
)
from polygraphml.errors import PolygraphError


class AgentHypothesisProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_key: str = Field(pattern=r"^h[1-3]$")
    mechanism: FindingMechanism
    features: list[str] = Field(min_length=1, max_length=5)
    assumptions: list[str] = Field(min_length=1, max_length=6)
    rationale_summary: str = Field(min_length=10, max_length=800)
    requested_probe: ProbeKind
    falsification_condition: str = Field(min_length=5, max_length=500)
    source_refs: list[str] = Field(default_factory=list, max_length=10)


class AgentQuestionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=5, max_length=300)
    why_it_matters: str = Field(min_length=5, max_length=500)
    answer_type: str = Field(pattern=r"^(single_choice|free_text)$")
    options: list[str] = Field(default_factory=list, max_length=6)
    affected_hypothesis_keys: list[str] = Field(min_length=1, max_length=1)
    blocking: bool = True


class AgentInvestigationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypotheses: list[AgentHypothesisProposal] = Field(min_length=1, max_length=3)
    question: AgentQuestionProposal | None = None
    reasoning_summary: str = Field(min_length=10, max_length=1000)


@dataclass(slots=True)
class AuditAgentContext:
    scenario: Scenario
    dataset_profile: DatasetProfile
    notebook_summary: dict[str, object]
    supported_probes: tuple[ProbeKind, ...]
    candidate_features: tuple[str, ...]
    feature_context: dict[str, str]


@dataclass(frozen=True, slots=True)
class AgentInvestigationResult:
    plan: AgentInvestigationPlan
    execution: AgentExecutionProvenance


PROBE_COMPATIBILITY: dict[FindingMechanism, frozenset[ProbeKind]] = {
    FindingMechanism.POST_OUTCOME: frozenset({ProbeKind.FEATURE_AVAILABILITY}),
    FindingMechanism.TARGET_PROXY: frozenset({ProbeKind.TARGET_PROXY_ASSOCIATION}),
    FindingMechanism.METRIC_MISMATCH: frozenset({ProbeKind.METRIC_CONTRACT}),
}


def sanitize_dataset_profile(profile: DatasetProfile) -> DatasetProfile:
    """Remove example values before the profile crosses the model boundary."""
    return profile.model_copy(
        update={
            "columns": [
                column.model_copy(update={"sample_values": []}) for column in profile.columns
            ]
        }
    )


@function_tool(timeout=3.0)
async def inspect_scenario(context: RunContextWrapper[AuditAgentContext]) -> str:
    """Return the declared prediction scenario and no private dataset rows."""
    return context.context.scenario.model_dump_json()


@function_tool(timeout=3.0)
async def inspect_dataset_profile(context: RunContextWrapper[AuditAgentContext]) -> str:
    """Return the sanitized dataset profile, including columns but not raw rows."""
    return context.context.dataset_profile.model_dump_json()


@function_tool(timeout=3.0)
async def inspect_notebook_summary(context: RunContextWrapper[AuditAgentContext]) -> str:
    """Return static notebook findings and source references without executing submitted code."""
    return json.dumps(context.context.notebook_summary, sort_keys=True)


@function_tool(timeout=3.0)
async def list_supported_probes(context: RunContextWrapper[AuditAgentContext]) -> str:
    """Return the deterministic probes available for this audit."""
    return json.dumps(
        {
            "probes": [probe.value for probe in context.context.supported_probes],
            "candidate_features": context.context.candidate_features,
            "feature_context": context.context.feature_context,
        }
    )


AUDIT_INSTRUCTIONS = """
You are PolygraphML's single semantic audit investigator. Audit the trained model,
evaluation data, notebook evidence, and declared prediction scenario as one system.

Inspect the supplied context before proposing one to three ranked, falsifiable
hypotheses. Select only candidate features and mechanism/probe combinations exposed
by the supported-probe tool. Use stable hypothesis keys h1, h2, and h3 in rank order.
Each hypothesis must state assumptions, concise rationale, a falsification condition,
and source references. Ask exactly one concise blocking question about the highest-value
missing fact, and link it to exactly one hypothesis key. The answer must be capable of
changing that hypothesis's status. Do not accuse, invent metrics, or treat association
or ablation alone as proof of leakage. Quantitative evidence and finding transitions
belong to deterministic application code. Return only the structured plan.
""".strip()


def create_audit_agent(settings: Settings) -> Agent[AuditAgentContext]:
    return Agent[AuditAgentContext](
        name="PolygraphML Audit Agent",
        instructions=AUDIT_INSTRUCTIONS,
        model=settings.openai_model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto"),
            verbosity="low",
            store=False,
        ),
        tools=[
            inspect_scenario,
            inspect_dataset_profile,
            inspect_notebook_summary,
            list_supported_probes,
        ],
        output_type=AgentInvestigationPlan,
    )


def validate_investigation_plan(
    context: AuditAgentContext, plan: AgentInvestigationPlan
) -> AgentInvestigationPlan:
    keys = [hypothesis.hypothesis_key for hypothesis in plan.hypotheses]
    if len(keys) != len(set(keys)):
        raise PolygraphError(
            "MODEL_OUTPUT_INVALID", "Hypothesis keys must be unique.", status_code=502
        )
    supported = {ProbeKind(probe) for probe in context.supported_probes}
    for hypothesis in plan.hypotheses:
        if not set(hypothesis.features).issubset(context.candidate_features):
            raise PolygraphError(
                "MODEL_OUTPUT_INVALID",
                "A hypothesis referenced a feature outside model feature order.",
                status_code=502,
            )
        compatible = PROBE_COMPATIBILITY.get(hypothesis.mechanism, frozenset())
        if (
            hypothesis.requested_probe not in supported
            or hypothesis.requested_probe not in compatible
        ):
            raise PolygraphError(
                "MODEL_OUTPUT_INVALID",
                "A hypothesis requested an unsupported mechanism/probe combination.",
                status_code=502,
            )
    if plan.question is None:
        raise PolygraphError(
            "MODEL_OUTPUT_INVALID",
            "The live investigation must request material scenario context.",
            status_code=502,
        )
    if plan.question.affected_hypothesis_keys[0] not in set(keys):
        raise PolygraphError(
            "MODEL_OUTPUT_INVALID",
            "The question referenced an unknown hypothesis key.",
            status_code=502,
        )
    return plan


async def run_live_investigation(
    settings: Settings,
    context: AuditAgentContext,
    audit_id: str,
) -> AgentInvestigationResult:
    if not settings.live_agent_ready or settings.openai_api_key is None:
        raise PolygraphError(
            "OPENAI_NOT_CONFIGURED",
            "Live semantic analysis requires OPENAI_API_KEY.",
            status_code=503,
        )
    set_default_openai_key(settings.openai_api_key.get_secret_value(), use_for_tracing=True)
    agent = create_audit_agent(settings)
    trace_id = gen_trace_id()
    started = time.perf_counter()
    try:
        result = await Runner.run(
            agent,
            "Inspect the submitted evidence and produce the next investigation plan.",
            context=context,
            max_turns=5,
            run_config=RunConfig(
                model=settings.openai_model,
                workflow_name="PolygraphML audit investigation",
                group_id=audit_id,
                trace_id=trace_id,
                trace_include_sensitive_data=False,
                trace_metadata={"audit_id": audit_id, "prompt_schema_version": "audit-v2"},
            ),
        )
    except Exception as exc:
        raise PolygraphError(
            "MODEL_OUTPUT_INVALID",
            "The live semantic investigation did not produce a valid plan.",
            status_code=502,
            detail={"reason": type(exc).__name__},
        ) from exc
    output = result.final_output
    if not isinstance(output, AgentInvestigationPlan):
        raise PolygraphError("MODEL_OUTPUT_INVALID", "Agent returned an unexpected output type.")
    usage = result.context_wrapper.usage
    last_response = result.raw_responses[-1] if result.raw_responses else None
    execution = AgentExecutionProvenance(
        provider="openai",
        mode="live",
        requested_model=settings.openai_model,
        # The application uses an explicit model slug rather than a moving alias.
        resolved_model=settings.openai_model,
        reasoning_effort="high",
        harness_version="audit-v2",
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
        trace_id=trace_id,
        response_id=last_response.response_id if last_response else None,
        request_id=last_response.request_id if last_response else None,
    )
    return AgentInvestigationResult(
        plan=validate_investigation_plan(context, output), execution=execution
    )


def fixture_investigation(
    feature: str = "call_duration",
    mechanism: FindingMechanism = FindingMechanism.POST_OUTCOME,
) -> AgentInvestigationPlan:
    requested_probe = (
        ProbeKind.TARGET_PROXY_ASSOCIATION
        if mechanism == FindingMechanism.TARGET_PROXY
        else ProbeKind.METRIC_CONTRACT
        if mechanism == FindingMechanism.METRIC_MISMATCH
        else ProbeKind.FEATURE_AVAILABILITY
    )
    question_text = (
        f"Is {feature} derived from, assigned after, or independent of the prediction target?"
        if mechanism == FindingMechanism.TARGET_PROXY
        else f"Is {feature} available at the declared decision moment, or only afterward?"
    )
    question_options = (
        ["independent", "derived_from_target", "assigned_after_outcome", "unknown"]
        if mechanism == FindingMechanism.TARGET_PROXY
        else ["before", "after", "depends", "unknown"]
    )
    return AgentInvestigationPlan(
        hypotheses=[
            AgentHypothesisProposal(
                hypothesis_key="h1",
                mechanism=mechanism,
                features=[feature],
                assumptions=[
                    "The feature provenance must be independent of the target."
                    if mechanism == FindingMechanism.TARGET_PROXY
                    else "The feature must exist at the declared prediction moment."
                ],
                rationale_summary=(
                    f"The provenance of {feature} may encode the target, so its derivation must be "
                    "established before association evidence can be interpreted."
                    if mechanism == FindingMechanism.TARGET_PROXY
                    else f"The semantic meaning of {feature} may imply post-decision information, "
                    "so its availability must be established from the declared use scenario."
                ),
                requested_probe=requested_probe,
                falsification_condition=(
                    f"{feature} is documented as an independent input not derived from the target."
                    if mechanism == FindingMechanism.TARGET_PROXY
                    else f"{feature} is reliably available at or before the declared decision moment."
                ),
                source_refs=[f"dataset:{feature}", "scenario:decision_time"],
            )
        ],
        question=AgentQuestionProposal(
            text=question_text,
            why_it_matters=(
                "Feature provenance determines whether strong association is a target-derived proxy."
                if mechanism == FindingMechanism.TARGET_PROXY
                else "Feature availability at the decision point determines whether this is "
                "post-outcome leakage."
            ),
            answer_type="single_choice",
            options=question_options,
            affected_hypothesis_keys=["h1"],
            blocking=True,
        ),
        reasoning_summary=(
            f"The submitted score should be reproduced first, then {feature} provenance should be "
            "resolved before association is interpreted."
            if mechanism == FindingMechanism.TARGET_PROXY
            else f"The submitted score should be reproduced first, then {feature} availability "
            "should be resolved before the feature is tested or classified."
        ),
    )
