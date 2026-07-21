from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polygraphml.agent.runtime import (
    AgentHypothesisProposal,
    AgentInvestigationPlan,
    AgentQuestionProposal,
    AuditAgentContext,
    fixture_investigation,
    sanitize_dataset_profile,
    validate_investigation_plan,
)
from polygraphml.benchmarks.catalog import POST_OUTCOME_BENCHMARK_ID
from polygraphml.config import Settings
from polygraphml.domain.ids import new_id
from polygraphml.domain.models import (
    Actor,
    AdapterStatus,
    Artifact,
    ArtifactKind,
    Audit,
    AuditEvent,
    AuditMode,
    AuditStatus,
    DatasetColumnProfile,
    DatasetProfile,
    EventType,
    Finding,
    FindingMechanism,
    FindingStatus,
    ProbeKind,
    ProjectSource,
    Scenario,
    Severity,
    SourceType,
)
from polygraphml.errors import PolygraphError
from polygraphml.operations.live_trace import build_sanitized_live_trace, run_live_smoke
from polygraphml.operations.public_github_gate import (
    PublicGitHubGateReport,
    run_public_github_gate,
)
from polygraphml.operations.queue_timing import (
    recommend_queue_timing,
    report_from_benchmark,
)


def test_agent_profile_removes_sample_values() -> None:
    profile = DatasetProfile(
        artifact_id="art_1",
        row_count=2,
        column_count=1,
        columns=[
            DatasetColumnProfile(
                name="sensitive",
                dtype="object",
                missing_fraction=0,
                cardinality=2,
                sample_values=["private-a", "private-b"],
            )
        ],
        sha256="a" * 64,
    )
    sanitized = sanitize_dataset_profile(profile)
    assert sanitized.columns[0].sample_values == []
    assert profile.columns[0].sample_values == ["private-a", "private-b"]


def test_live_agent_requires_a_non_empty_key() -> None:
    assert Settings(agent_mode="live", openai_api_key="").live_agent_ready is False
    assert Settings(agent_mode="live", openai_api_key="test-only-key").live_agent_ready is True
    assert Settings(agent_mode="fixture", openai_api_key="test-only-key").live_agent_ready is False


def test_live_plan_is_constrained_to_shipped_primary_probe() -> None:
    profile = DatasetProfile(
        artifact_id="art_1",
        row_count=2,
        column_count=1,
        columns=[
            DatasetColumnProfile(
                name="call_duration",
                dtype="float64",
                missing_fraction=0,
                cardinality=2,
            )
        ],
        sha256="a" * 64,
    )
    context = AuditAgentContext(
        scenario=Scenario(
            revision=1,
            target_definition="Customer churn",
            row_entity="One customer",
            decision_time="Before a campaign call",
            prediction_horizon="30 days",
            split_unit="customer_id",
            intended_metric="roc_auc",
        ),
        dataset_profile=profile,
        notebook_summary={},
        supported_probes=("feature_availability",),
        candidate_features=("call_duration",),
        feature_context={},
    )
    valid = fixture_investigation("call_duration")
    assert validate_investigation_plan(context, valid) is valid

    invalid = fixture_investigation("unknown_feature")
    with pytest.raises(PolygraphError, match="outside model feature order"):
        validate_investigation_plan(context, invalid)


def test_live_plan_accepts_ranked_supported_mechanisms() -> None:
    profile = DatasetProfile(
        artifact_id="art_1",
        row_count=20,
        column_count=2,
        columns=[
            DatasetColumnProfile(
                name="engagement_band",
                dtype="str",
                missing_fraction=0,
                cardinality=3,
            ),
            DatasetColumnProfile(
                name="call_duration",
                dtype="float64",
                missing_fraction=0,
                cardinality=20,
            ),
        ],
        sha256="b" * 64,
    )
    context = AuditAgentContext(
        scenario=Scenario(
            revision=1,
            target_definition="Customer subscribes",
            row_entity="One campaign contact",
            decision_time="Before contact begins",
            prediction_horizon="Current campaign",
            split_unit="customer_id",
            intended_metric="roc_auc",
        ),
        dataset_profile=profile,
        notebook_summary={},
        supported_probes=(
            ProbeKind.TARGET_PROXY_ASSOCIATION,
            ProbeKind.FEATURE_AVAILABILITY,
        ),
        candidate_features=("engagement_band", "call_duration"),
        feature_context={"engagement_band": "Operational band assigned after subscription."},
    )
    plan = AgentInvestigationPlan(
        hypotheses=[
            AgentHypothesisProposal(
                hypothesis_key="h1",
                mechanism=FindingMechanism.TARGET_PROXY,
                features=["engagement_band"],
                assumptions=["The band may encode the target."],
                rationale_summary="The feature definition describes a post-subscription assignment.",
                requested_probe=ProbeKind.TARGET_PROXY_ASSOCIATION,
                falsification_condition="The band is independently assigned before prediction.",
                source_refs=["manifest:features.engagement_band"],
            ),
            AgentHypothesisProposal(
                hypothesis_key="h2",
                mechanism=FindingMechanism.POST_OUTCOME,
                features=["call_duration"],
                assumptions=["Prediction occurs before the call."],
                rationale_summary="Current-call duration may not exist at selection time.",
                requested_probe=ProbeKind.FEATURE_AVAILABILITY,
                falsification_condition="The decision is made after the call.",
                source_refs=["scenario:decision_time"],
            ),
        ],
        question=AgentQuestionProposal(
            text="How is engagement_band assigned relative to subscription?",
            why_it_matters="Its provenance determines whether it can encode the target.",
            answer_type="single_choice",
            options=["independent", "derived_from_target", "unknown"],
            affected_hypothesis_keys=["h1"],
        ),
        reasoning_summary="Two semantic mechanisms are plausible and the proxy provenance matters most.",
    )
    assert validate_investigation_plan(context, plan) is plan


def test_live_plan_rejects_incompatible_mechanism_probe() -> None:
    profile = DatasetProfile(
        artifact_id="art_1",
        row_count=2,
        column_count=1,
        columns=[
            DatasetColumnProfile(
                name="feature",
                dtype="float64",
                missing_fraction=0,
                cardinality=2,
            )
        ],
        sha256="c" * 64,
    )
    context = AuditAgentContext(
        scenario=Scenario(
            revision=1,
            target_definition="Outcome",
            row_entity="One row",
            decision_time="Before outcome",
            prediction_horizon="One day",
            split_unit="entity",
            intended_metric="roc_auc",
        ),
        dataset_profile=profile,
        notebook_summary={},
        supported_probes=(ProbeKind.FEATURE_AVAILABILITY,),
        candidate_features=("feature",),
        feature_context={},
    )
    invalid = fixture_investigation("feature", FindingMechanism.TARGET_PROXY)
    with pytest.raises(PolygraphError, match="unsupported mechanism/probe"):
        validate_investigation_plan(context, invalid)


def test_queue_timing_distinguishes_fixture_from_live_calibration() -> None:
    fixture = recommend_queue_timing(
        [0.1, 0.2, 0.3],
        measurement_mode="fixture",
        configured_visibility_seconds=300,
    )
    assert fixture.recommended_visibility_seconds == 60
    assert fixture.configured_heartbeat_seconds == 60
    assert fixture.configured_covers_measurement is True
    assert fixture.production_calibrated is False

    live = recommend_queue_timing(
        [40.0] * 20,
        measurement_mode="live",
        configured_visibility_seconds=300,
    )
    assert live.recommended_visibility_seconds == 190
    assert live.production_calibrated is True


def test_queue_timing_reads_captured_benchmark(tmp_path: Path) -> None:
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps(
            {
                "mode": "fixture",
                "cases": [
                    {"latency_seconds": 0.25},
                    {"latency_seconds": 0.5},
                ],
            }
        )
    )
    report = report_from_benchmark(path, configured_visibility_seconds=300)
    assert report.case_count == 2
    assert report.observed_p95_seconds == 0.5


def test_queue_timing_reads_deployed_smoke_runs(tmp_path: Path) -> None:
    path = tmp_path / "deployed-smoke.json"
    path.write_text(
        json.dumps(
            {
                "mode": "live",
                "runs": [{"duration_seconds": 25.0} for _ in range(20)],
            }
        )
    )
    report = report_from_benchmark(path, configured_visibility_seconds=300)
    assert report.case_count == 20
    assert report.production_calibrated is True


async def test_live_smoke_orchestration_with_mocked_model_boundary(
    monkeypatch,
) -> None:
    async def fake_live_investigation(*args, **kwargs):
        return fixture_investigation("call_duration")

    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setattr(
        "polygraphml.worker.coordinator.run_live_investigation",
        fake_live_investigation,
    )
    trace = await run_live_smoke()
    assert trace.final_status == "complete"
    assert trace.actor_counts["agent"] >= 1
    assert trace.trace_include_sensitive_data is False
    assert trace.payloads_included is False


def test_sanitized_trace_contains_metadata_not_event_payloads() -> None:
    audit = Audit(
        audit_id="aud_1",
        project_id="prj_1",
        session_id="ses_1",
        scenario_revision=1,
        mode=AuditMode.COMPLETE,
        status=AuditStatus.COMPLETE,
        last_event_sequence=1,
    )
    event = AuditEvent(
        event_id="evt_1",
        audit_id=audit.audit_id,
        sequence=1,
        type=EventType.REASONING_SUMMARY,
        actor=Actor.AGENT,
        created_at=datetime.now(UTC),
        payload={"summary": "must not be copied to the developer artifact"},
    )
    finding = Finding(
        finding_id="fnd_1",
        mechanism=FindingMechanism.POST_OUTCOME,
        features=["feature"],
        status=FindingStatus.CONFIRMED,
        severity=Severity.HIGH,
        confidence=0.9,
        conclusion="confirmed",
        what_would_change_this="new timing evidence",
    )
    trace = build_sanitized_live_trace(audit, [event], [finding], "gpt-5.6-sol")
    rendered = trace.model_dump_json()
    assert "must not be copied" not in rendered
    assert trace.actor_counts == {"agent": 1}
    assert trace.confirmed_mechanisms == ["post_outcome"]
    assert trace.payloads_included is False


async def test_public_github_gate_rejects_mutable_or_short_refs() -> None:
    with pytest.raises(ValueError, match="full lowercase 40-character"):
        await run_public_github_gate("https://github.com/Iguta/polygraph-ml", "main")


async def test_public_github_gate_runs_immutable_manifest_audit(monkeypatch) -> None:
    commit = "c" * 40

    async def create_fixture_github_project(service, session, name, repository_url, ref):
        del name
        project = service.create_benchmark_project(session, POST_OUTCOME_BENCHMARK_ID)
        project.source = ProjectSource(
            type=SourceType.GITHUB,
            repository_url=repository_url,
            requested_ref=ref,
            resolved_commit=ref,
        )
        for artifact_id in project.artifact_ids:
            artifact = service.repository.get(Artifact, artifact_id)
            assert artifact is not None
            artifact.source_ref = f"github:fixtures/{artifact.filename}@{ref}"
            service.repository.put(artifact)
        manifest = Artifact(
            artifact_id=new_id("art"),
            project_id=project.project_id,
            kind=ArtifactKind.MANIFEST,
            filename=".polygraphml.yml",
            sha256="d" * 64,
            size_bytes=100,
            media_type="application/yaml",
            storage_key="fixture/manifest",
            adapter="polygraphml-yaml",
            adapter_status=AdapterStatus.SUPPORTED,
            source_ref=f"github:.polygraphml.yml@{ref}",
        )
        service.repository.put(manifest)
        project.artifact_ids.append(manifest.artifact_id)
        return service.repository.put(project)

    monkeypatch.setattr(
        "polygraphml.services.projects.ProjectService.create_github_project",
        create_fixture_github_project,
    )
    report = await run_public_github_gate(
        "https://github.com/Iguta/polygraph-ml",
        commit,
        expected_pair="post_outcome:call_duration",
    )

    assert report.requested_commit == commit
    assert report.resolved_commit == commit
    assert report.confirmed_pairs == ["post_outcome:call_duration"]
    assert report.corrected_metric < report.reproduced_metric
    assert report.payloads_included is False


def test_public_github_gate_report_requires_complete_sanitized_evidence() -> None:
    report = PublicGitHubGateReport(
        created_at=datetime.now(UTC),
        repository_url="https://github.com/Iguta/polygraph-ml",
        requested_commit="a" * 40,
        resolved_commit="a" * 40,
        artifact_count=5,
        artifact_hashes={".polygraphml.yml": "b" * 64},
        audit_status="complete",
        event_count=20,
        confirmed_pairs=["post_outcome:duration"],
        metric="roc_auc",
        reported_metric=0.871301,
        reproduced_metric=0.8713005400607956,
        corrected_metric=0.7330845871361364,
    )
    rendered = report.model_dump_json()
    assert "access_token" not in rendered
    assert report.payloads_included is False
    assert report.sensitive_data_included is False
