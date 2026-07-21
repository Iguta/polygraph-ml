from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from polygraphml.domain.models import (
    Artifact,
    ArtifactKind,
    ArtifactMapping,
    Audit,
    AuditEvent,
    AuditMode,
    Finding,
    Project,
    Question,
    RepairBundle,
    Scenario,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceInput(ApiModel):
    type: Literal["github", "upload"]
    repository_url: HttpUrl | None = None
    ref: str = "main"


class CreateProjectRequest(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    source: SourceInput


class BenchmarkProjectRequest(ApiModel):
    benchmark_id: str


class UploadArtifactInput(ApiModel):
    client_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    filename: str
    kind: ArtifactKind
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str


class PresignRequest(ApiModel):
    artifacts: list[UploadArtifactInput] = Field(min_length=1, max_length=12)


class CompleteUploadsRequest(ApiModel):
    artifact_ids: list[str] = Field(min_length=1, max_length=12)


class MappingRequest(ArtifactMapping):
    pass


class ScenarioRequest(Scenario):
    revision: int = 1


class StartAuditRequest(ApiModel):
    project_id: str
    scenario_revision: int = Field(ge=1)
    mode: AuditMode


class AnswerRequest(ApiModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=1000)
    scenario_patch: dict[str, str] | None = None


class ReportRequest(ApiModel):
    audience: Literal["technical", "executive"]
    format: Literal["markdown"] = "markdown"


class ErrorBody(ApiModel):
    code: str
    message: str
    detail: dict[str, Any]
    request_id: str


class SuccessEnvelope[ResponseT](ApiModel):
    data: ResponseT
    error: None = None


class ProjectResponse(Project):
    artifacts: list[Artifact]


class AuditResponse(Audit):
    findings: list[Finding]
    open_questions: list[Question]
    events_url: str


class SessionResponse(ApiModel):
    access_token: str
    expires_at: datetime
    limits: dict[str, int]


class ReadinessResponse(ApiModel):
    status: Literal["ready"]
    agent_mode: Literal["fixture", "live"]
    live_agent_ready: bool


class VersionResponse(ApiModel):
    api_version: str
    release_version: str
    build_sha: str
    evaluator_version: str


class RepairBundleResponse(RepairBundle):
    download_url: str | None = None


class DecisionTraceResponse(ApiModel):
    events: list[AuditEvent]


def success[ResponseT](data: ResponseT) -> dict[str, ResponseT | None]:
    return {"data": data, "error": None}
