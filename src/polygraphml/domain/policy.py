from __future__ import annotations

from dataclasses import dataclass

from polygraphml.domain.models import FindingStatus


@dataclass(frozen=True, slots=True)
class ConfirmationEvidence:
    scenario_established: bool
    mechanism_evidence_count: int
    impact_measured: bool
    protocol_invalidating: bool = False
    contradictions_resolved: bool = False
    ablation_delta: float | None = None


def decide_finding_status(evidence: ConfirmationEvidence) -> FindingStatus:
    """Apply the evidence policy without allowing ablation alone to prove leakage."""
    if not evidence.scenario_established:
        return FindingStatus.NEEDS_CONTEXT
    if evidence.mechanism_evidence_count == 0:
        return FindingStatus.TESTED if evidence.impact_measured else FindingStatus.SUSPECTED
    if not evidence.contradictions_resolved:
        return FindingStatus.INCONCLUSIVE
    if evidence.impact_measured or evidence.protocol_invalidating:
        return FindingStatus.CONFIRMED
    return FindingStatus.TESTED
