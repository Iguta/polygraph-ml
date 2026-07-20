from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)


class SourceType(StrEnum):
    GITHUB = "github"
    UPLOAD = "upload"
    BENCHMARK = "benchmark"


class ProjectStatus(StrEnum):
    IMPORTING = "importing"
    READY_FOR_UPLOAD = "ready_for_upload"
    VALIDATING = "validating"
    READY_FOR_MAPPING = "ready_for_mapping"
    READY = "ready"
    PREFLIGHT_ONLY = "preflight_only"
    REJECTED = "rejected"


class ArtifactKind(StrEnum):
    DATASET = "dataset"
    MODEL = "model"
    NOTEBOOK = "notebook"
    SOURCE = "source"
    MANIFEST = "manifest"


class AdapterStatus(StrEnum):
    SUPPORTED = "supported"
    LIMITED = "limited"
    UNSUPPORTED = "unsupported"
    REJECTED = "rejected"


class AuditMode(StrEnum):
    COMPLETE = "complete_audit"
    PREFLIGHT = "dataset_preflight"


class AuditStatus(StrEnum):
    VALIDATING = "validating"
    QUEUED = "queued"
    RECONSTRUCTING = "reconstructing"
    REPRODUCING = "reproducing"
    INTERROGATING = "interrogating"
    WAITING_FOR_USER = "waiting_for_user"
    PROBING = "probing"
    CORRECTING = "correcting"
    COMPOSING = "composing"
    COMPLETE = "complete"
    FAILED_PARTIAL = "failed_partial"
    FAILED = "failed"


TERMINAL_AUDIT_STATUSES = {
    AuditStatus.COMPLETE,
    AuditStatus.FAILED_PARTIAL,
    AuditStatus.FAILED,
}


class ReproductionTier(StrEnum):
    EXACT_SUPPORTED = "exact_supported"
    CONTROLLED_RECONSTRUCTION = "controlled_reconstruction"
    REFERENCE_CHALLENGER = "reference_challenger"
    STATIC_ONLY = "static_only"


class FindingStatus(StrEnum):
    NEEDS_CONTEXT = "needs_context"
    SUSPECTED = "suspected"
    TESTED = "tested"
    CONFIRMED = "confirmed"
    CLEARED = "cleared"
    INCONCLUSIVE = "inconclusive"


class FindingMechanism(StrEnum):
    POST_OUTCOME = "post_outcome"
    TARGET_PROXY = "target_proxy"
    SPLIT_CONTAMINATION = "split_contamination"
    GROUP_CONTAMINATION = "group_contamination"
    TEMPORAL = "temporal"
    PREPROCESSING = "preprocessing"
    METRIC_MISMATCH = "metric_mismatch"
    OTHER = "other"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Actor(StrEnum):
    USER = "user"
    AGENT = "agent"
    TOOL = "tool"
    SYSTEM = "system"


class EventType(StrEnum):
    AUDIT_STATE = "audit_state"
    ASSUMPTION = "assumption"
    QUESTION = "question"
    ANSWER = "answer"
    HYPOTHESIS = "hypothesis"
    TOOL_STARTED = "tool_started"
    TOOL_RESULT = "tool_result"
    EVIDENCE = "evidence"
    CORRECTION = "correction"
    FINDING_CHANGED = "finding_changed"
    REASONING_SUMMARY = "reasoning_summary"
    WARNING = "warning"
    RETRY = "retry"
    ERROR = "error"
    VERDICT = "verdict"


class TrustState(StrEnum):
    MATERIALLY_INFLATED = "materially_inflated"
    PARTIALLY_SUPPORTED = "partially_supported"
    SUPPORTED = "supported"
    INCONCLUSIVE = "inconclusive"


class Session(StrictModel):
    session_id: str
    token_hash: str
    expires_at: datetime
    max_projects: int = 3
    max_live_audits: int = 2
    created_at: datetime = Field(default_factory=utc_now)


class ProjectSource(StrictModel):
    type: SourceType
    repository_url: HttpUrl | None = None
    requested_ref: str | None = None
    resolved_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    benchmark_id: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> ProjectSource:
        if self.type == SourceType.GITHUB and self.repository_url is None:
            raise ValueError("repository_url is required for a GitHub source")
        if self.type == SourceType.BENCHMARK and not self.benchmark_id:
            raise ValueError("benchmark_id is required for a benchmark source")
        return self


class Artifact(StrictModel):
    artifact_id: str
    project_id: str
    kind: ArtifactKind
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str
    storage_key: str
    adapter: str
    adapter_status: AdapterStatus
    validation_notes: list[str] = Field(default_factory=list)
    source_ref: str | None = None
    client_id: str | None = None
    upload_status: Literal["pending", "complete"] = "complete"
    created_at: datetime = Field(default_factory=utc_now)


class ReportedMetricSource(StrictModel):
    artifact_id: str
    location: str


class ArtifactMapping(StrictModel):
    dataset_artifact_id: str | None = None
    model_artifact_id: str | None = None
    notebook_artifact_id: str | None = None
    target_column: str | None = None
    time_column: str | None = None
    entity_column: str | None = None
    split_column: str | None = None
    reported_metric_source: ReportedMetricSource | None = None


class Scenario(StrictModel):
    revision: int = Field(ge=1)
    target_definition: str = Field(min_length=3, max_length=500)
    row_entity: str = Field(min_length=2, max_length=300)
    decision_time: str = Field(min_length=3, max_length=500)
    prediction_horizon: str = Field(min_length=1, max_length=200)
    split_unit: str = Field(min_length=1, max_length=200)
    intended_metric: Literal["roc_auc", "accuracy", "f1"]
    positive_label: str = "1"
    notes: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=utc_now)


class Project(StrictModel):
    project_id: str
    session_id: str
    name: str = Field(min_length=1, max_length=120)
    source: ProjectSource
    status: ProjectStatus
    artifact_ids: list[str] = Field(default_factory=list)
    mapping: ArtifactMapping = Field(default_factory=ArtifactMapping)
    scenarios: list[Scenario] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def current_scenario(self) -> Scenario | None:
        return self.scenarios[-1] if self.scenarios else None


class DatasetColumnProfile(StrictModel):
    name: str
    dtype: str
    missing_fraction: float = Field(ge=0, le=1)
    cardinality: int = Field(ge=0)
    sample_values: list[str] = Field(default_factory=list, max_length=5)


class DatasetProfile(StrictModel):
    artifact_id: str
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    columns: list[DatasetColumnProfile]
    target_balance: dict[str, float] = Field(default_factory=dict)
    sha256: str


class Hypothesis(StrictModel):
    hypothesis_id: str
    mechanism: FindingMechanism
    features: list[str]
    assumptions: list[str]
    rationale_summary: str
    requested_probe: str
    falsification_condition: str
    source_refs: list[str] = Field(default_factory=list)


class Evidence(StrictModel):
    evidence_id: str
    hypothesis_id: str | None = None
    probe: str
    tool_version: str
    observation: str
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=utc_now)


class Correction(StrictModel):
    correction_id: str
    kind: str
    description: str
    features_removed: list[str] = Field(default_factory=list)
    protocol_id: str
    evidence_ids: list[str] = Field(default_factory=list)


class Finding(StrictModel):
    finding_id: str
    mechanism: FindingMechanism
    features: list[str]
    status: FindingStatus
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    conclusion: str
    hypothesis_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    correction_id: str | None = None
    what_would_change_this: str


class MetricValue(StrictModel):
    value: float
    provenance: str
    protocol_id: str | None = None
    tolerance: float | None = Field(default=None, ge=0)


class MetricComparison(StrictModel):
    metric: Literal["roc_auc", "accuracy", "f1"]
    reported: MetricValue | None = None
    reproduced: MetricValue | None = None
    corrected: MetricValue | None = None
    reproduction_status: Literal[
        "within_tolerance", "outside_tolerance", "unavailable", "not_claimed"
    ]


class Question(StrictModel):
    question_id: str
    audit_id: str
    text: str
    why_it_matters: str
    affected_hypothesis_ids: list[str]
    answer_type: Literal["single_choice", "free_text"]
    options: list[str] = Field(default_factory=list)
    blocking: bool
    status: Literal["open", "answered"] = "open"
    answer: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    answered_at: datetime | None = None


class Verdict(StrictModel):
    trust_state: TrustState
    summary: str
    finding_counts: dict[str, int]
    unsupported_checks: list[str] = Field(default_factory=list)


class Provenance(StrictModel):
    source_commit: str | None = None
    artifact_hashes: list[str] = Field(default_factory=list)
    evaluator_version: str = "0.1.0"
    agent_model: str = "gpt-5.6-sol"
    prompt_schema_version: str = "audit-v1"
    random_seed: int = 42
    package_versions: dict[str, str] = Field(default_factory=dict)
    split_hash: str | None = None
    feature_order: list[str] = Field(default_factory=list)


class Audit(StrictModel):
    audit_id: str
    project_id: str
    session_id: str
    scenario_revision: int
    mode: AuditMode
    status: AuditStatus
    reproduction_tier: ReproductionTier | None = None
    hypothesis_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    correction_ids: list[str] = Field(default_factory=list)
    question_ids: list[str] = Field(default_factory=list)
    metric_comparison: MetricComparison | None = None
    verdict: Verdict | None = None
    provenance: Provenance = Field(default_factory=Provenance)
    last_event_sequence: int = 0
    checkpoint: str = "created"
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuditEvent(StrictModel):
    event_id: str
    audit_id: str
    sequence: int = Field(ge=1)
    type: EventType
    actor: Actor
    created_at: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any]
    provenance_refs: list[str] = Field(default_factory=list)


class JobMessage(StrictModel):
    audit_id: str
    operation: Literal["start", "resume"]
    schema_version: Literal["1"] = "1"
    idempotency_key: str = Field(min_length=8, max_length=200)


class BenchmarkExpectation(StrictModel):
    mechanism: FindingMechanism
    feature: str
    expected_status: FindingStatus


class BenchmarkDefinition(StrictModel):
    benchmark_id: str
    name: str
    description: str
    source_url: HttpUrl | None = None
    license_name: str
    license_url: HttpUrl | None = None
    version: str
    artifact_manifest: dict[ArtifactKind, str]
    artifact_hashes: dict[str, str]
    scenario: Scenario
    expectations: list[BenchmarkExpectation]
    metric_tolerance: float = Field(ge=0)
    expected_corrected_metric: float | None = None
    prohibited_claims: list[str]
    fixture: bool


class AuditReport(StrictModel):
    report_id: str
    audit_id: str
    audience: Literal["technical", "executive"]
    format: Literal["markdown"] = "markdown"
    content: str
    created_at: datetime = Field(default_factory=utc_now)
