from __future__ import annotations

import json
from dataclasses import dataclass

from agents import (
    Agent,
    ModelSettings,
    RunConfig,
    RunContextWrapper,
    Runner,
    function_tool,
    set_default_openai_key,
)
from openai.types.shared import Reasoning
from pydantic import BaseModel, ConfigDict, Field

from polygraphml.config import Settings
from polygraphml.domain.models import DatasetProfile, FindingMechanism, Scenario
from polygraphml.errors import PolygraphError


class AgentHypothesisProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mechanism: FindingMechanism
    features: list[str] = Field(min_length=1, max_length=5)
    assumptions: list[str] = Field(min_length=1, max_length=6)
    rationale_summary: str = Field(min_length=10, max_length=800)
    requested_probe: str = Field(min_length=2, max_length=80)
    falsification_condition: str = Field(min_length=5, max_length=500)
    source_refs: list[str] = Field(default_factory=list, max_length=10)


class AgentQuestionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=5, max_length=300)
    why_it_matters: str = Field(min_length=5, max_length=500)
    answer_type: str = Field(pattern=r"^(single_choice|free_text)$")
    options: list[str] = Field(default_factory=list, max_length=6)
    blocking: bool = True


class AgentInvestigationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypotheses: list[AgentHypothesisProposal] = Field(min_length=1, max_length=8)
    question: AgentQuestionProposal | None = None
    reasoning_summary: str = Field(min_length=10, max_length=1000)


@dataclass(slots=True)
class AuditAgentContext:
    scenario: Scenario
    dataset_profile: DatasetProfile
    notebook_summary: dict[str, object]
    supported_probes: tuple[str, ...]
    candidate_features: tuple[str, ...]


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
            "probes": context.context.supported_probes,
            "candidate_features": context.context.candidate_features,
        }
    )


AUDIT_INSTRUCTIONS = """
You are PolygraphML's single semantic audit investigator. Audit the model, data,
evaluation pipeline, and declared prediction scenario as one system.

Use the inspection tools before proposing a plan. For the P0 coordinator, the
primary hypothesis must use mechanism post_outcome, requested probe
feature_availability, and a feature from candidate_features. Produce falsifiable hypotheses,
not accusations. Every hypothesis must name its assumptions, a supported probe, a
falsification condition, and source references. Ask one concise question only when
its answer can materially change a conclusion. Never invent a metric or claim that
an ablation alone proves leakage. Quantitative evidence is owned by deterministic
tools outside this response. Return only the structured investigation plan.
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
    primary = plan.hypotheses[0]
    if primary.mechanism != FindingMechanism.POST_OUTCOME:
        raise PolygraphError(
            "MODEL_OUTPUT_INVALID",
            "The P0 coordinator requires a post-outcome primary hypothesis.",
            status_code=502,
        )
    if primary.requested_probe != "feature_availability":
        raise PolygraphError(
            "MODEL_OUTPUT_INVALID",
            "The P0 coordinator requires the feature_availability primary probe.",
            status_code=502,
        )
    if not set(primary.features).issubset(context.candidate_features):
        raise PolygraphError(
            "MODEL_OUTPUT_INVALID",
            "The primary hypothesis referenced a feature outside model feature order.",
            status_code=502,
        )
    if plan.question is None:
        raise PolygraphError(
            "MODEL_OUTPUT_INVALID",
            "The live investigation must request material scenario context.",
            status_code=502,
        )
    return plan


async def run_live_investigation(
    settings: Settings,
    context: AuditAgentContext,
    audit_id: str,
) -> AgentInvestigationPlan:
    if not settings.live_agent_ready or settings.openai_api_key is None:
        raise PolygraphError(
            "OPENAI_NOT_CONFIGURED",
            "Live semantic analysis requires OPENAI_API_KEY.",
            status_code=503,
        )
    set_default_openai_key(settings.openai_api_key.get_secret_value(), use_for_tracing=True)
    agent = create_audit_agent(settings)
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
                trace_include_sensitive_data=False,
                trace_metadata={"audit_id": audit_id, "prompt_schema_version": "audit-v1"},
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
    return validate_investigation_plan(context, output)


def fixture_investigation(feature: str = "call_duration") -> AgentInvestigationPlan:
    return AgentInvestigationPlan(
        hypotheses=[
            AgentHypothesisProposal(
                mechanism=FindingMechanism.POST_OUTCOME,
                features=[feature],
                assumptions=["The feature must exist at the declared prediction moment."],
                rationale_summary=(
                    f"The semantic meaning of {feature} may imply post-decision information, so its "
                    "availability must be established from the declared use scenario."
                ),
                requested_probe="feature_availability",
                falsification_condition=(
                    f"{feature} is reliably available at or before the declared decision moment."
                ),
                source_refs=[f"dataset:{feature}", "scenario:decision_time"],
            )
        ],
        question=AgentQuestionProposal(
            text=(f"Is {feature} available at the declared decision moment, or only afterward?"),
            why_it_matters=(
                "Feature availability at the decision point determines whether this is post-outcome "
                "leakage."
            ),
            answer_type="single_choice",
            options=["before", "after", "depends", "unknown"],
            blocking=True,
        ),
        reasoning_summary=(
            f"The submitted score should be reproduced first, then {feature} availability should be "
            "resolved before the feature is tested or classified."
        ),
    )
