from __future__ import annotations

import pandas as pd

from polygraphml.domain.models import FindingStatus
from polygraphml.domain.policy import ConfirmationEvidence, decide_finding_status
from polygraphml.engine.probes import (
    duplicate_overlap_evidence,
    feature_availability_evidence,
    feature_provenance_evidence,
    group_overlap_evidence,
    metric_contract_evidence,
    preprocessing_order_evidence,
    target_proxy_association_evidence,
)


def test_ablation_delta_alone_cannot_confirm_leakage() -> None:
    status = decide_finding_status(
        ConfirmationEvidence(
            scenario_established=True,
            mechanism_evidence_count=0,
            impact_measured=True,
            contradictions_resolved=True,
            ablation_delta=0.9,
        )
    )
    assert status == FindingStatus.TESTED


def test_policy_requires_context_and_resolved_contradictions() -> None:
    assert (
        decide_finding_status(ConfirmationEvidence(False, 1, True, contradictions_resolved=True))
        == FindingStatus.NEEDS_CONTEXT
    )
    assert (
        decide_finding_status(ConfirmationEvidence(True, 1, True, contradictions_resolved=False))
        == FindingStatus.INCONCLUSIVE
    )
    assert (
        decide_finding_status(ConfirmationEvidence(True, 1, True, contradictions_resolved=True))
        == FindingStatus.CONFIRMED
    )
    assert (
        decide_finding_status(ConfirmationEvidence(True, 1, False, contradictions_resolved=True))
        == FindingStatus.TESTED
    )


def test_feature_availability_is_scenario_evidence() -> None:
    evidence = feature_availability_evidence("hyp_1", "call_duration", "only after", ["user"])
    assert evidence.metrics["unavailable_at_decision"] is True
    assert evidence.source_refs == ["user"]

    unresolved = feature_availability_evidence("hyp_1", "call_duration", "unknown", ["user"])
    assert unresolved.metrics["available_at_decision"] is False
    assert unresolved.metrics["unavailable_at_decision"] is False
    assert unresolved.limitations


def test_target_proxy_requires_semantics_beyond_association() -> None:
    frame = pd.DataFrame(
        {
            "engagement_band": [0, 1, 0, 1, 0, 1, 0, 1],
            "target": [0, 1, 0, 1, 0, 1, 0, 1],
            "split": ["train"] * 4 + ["test"] * 4,
        }
    )
    association = target_proxy_association_evidence(
        "hyp_1",
        frame,
        "target",
        "split",
        "engagement_band",
        ["dataset:engagement_band"],
    )
    assert association.metrics["computed"] is True
    assert association.metrics["single_feature_auc"] == 1.0
    assert association.limitations
    assert (
        decide_finding_status(
            ConfirmationEvidence(
                scenario_established=True,
                mechanism_evidence_count=0,
                impact_measured=True,
                contradictions_resolved=True,
            )
        )
        == FindingStatus.TESTED
    )

    provenance = feature_provenance_evidence(
        "hyp_1", "engagement_band", "derived_from_target", ["user"]
    )
    assert provenance.metrics["target_derived"] is True


def test_metric_contract_reports_static_match_and_limit() -> None:
    evidence = metric_contract_evidence("hyp_1", "roc_auc", ["accuracy"], ["notebook#cell=2"])
    assert evidence.metrics["metric_matches"] is False
    assert evidence.limitations


def test_overlap_and_preprocessing_probes() -> None:
    frame = pd.DataFrame(
        {
            "entity": ["a", "b", "a", "c"],
            "value": [1, 2, 1, 4],
            "split": ["train", "train", "test", "test"],
        }
    )
    train = frame["split"] == "train"
    test = frame["split"] == "test"
    groups = group_overlap_evidence(frame["entity"], train, test)
    assert groups.metrics == {"overlap_count": 1, "has_overlap": True}

    duplicates = duplicate_overlap_evidence(frame[["value", "split"]], "split")
    assert duplicates.metrics == {"overlap_count": 1, "has_overlap": True}

    preprocessing = preprocessing_order_evidence(True, ["notebook#cell=1"])
    assert preprocessing.metrics["fit_before_split"] is True
    assert preprocessing.limitations
