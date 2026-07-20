from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

import uvicorn
from fastapi import Depends, FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from polygraphml.api.container import AppContainer, build_container
from polygraphml.api.dependencies import get_container, get_session, owned_audit, owned_project
from polygraphml.api.schemas import (
    AnswerRequest,
    BenchmarkProjectRequest,
    CompleteUploadsRequest,
    CreateProjectRequest,
    MappingRequest,
    PresignRequest,
    ReportRequest,
    ScenarioRequest,
    StartAuditRequest,
    success,
)
from polygraphml.config import Settings, get_settings
from polygraphml.domain.ids import new_id
from polygraphml.domain.models import (
    Artifact,
    Audit,
    AuditStatus,
    Finding,
    Project,
    Question,
    Session,
    SourceType,
)
from polygraphml.errors import PolygraphError
from polygraphml.storage.artifacts import UploadDeclaration


async def read_bounded_upload(request: Request, *, declared_size: int, maximum_size: int) -> bytes:
    limit = min(declared_size, maximum_size)
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            announced_size = int(content_length)
        except ValueError as exc:
            raise PolygraphError("INVALID_ARTIFACT", "Upload Content-Length is invalid.") from exc
        if announced_size < 0 or announced_size > limit:
            raise PolygraphError(
                "ARTIFACT_TOO_LARGE",
                "Upload exceeds its declared size or server limit.",
                status_code=413,
                detail={"max_bytes": limit},
            )
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > limit:
            raise PolygraphError(
                "ARTIFACT_TOO_LARGE",
                "Upload exceeds its declared size or server limit.",
                status_code=413,
                detail={"max_bytes": limit},
            )
    if len(content) != declared_size:
        raise PolygraphError(
            "INVALID_ARTIFACT",
            "Upload byte count does not match its declaration.",
            detail={"size_matches": False},
        )
    return bytes(content)


def create_app(settings: Settings | None = None, container: AppContainer | None = None) -> FastAPI:
    configured = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if not hasattr(application.state, "container"):
            application.state.container = container or build_container(configured)
        yield
        application.state.container.repository.close()

    application = FastAPI(
        title="PolygraphML API",
        version="0.1.0",
        lifespan=lifespan,
        default_response_class=JSONResponse,
    )
    application.state.container = container or build_container(configured)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(configured.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "Last-Event-ID"],
    )

    @application.exception_handler(PolygraphError)
    async def handle_polygraph_error(_: Request, exc: PolygraphError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "data": None,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "detail": exc.detail,
                    "request_id": new_id("req"),
                },
            },
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"location": ".".join(str(part) for part in error["loc"]), "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "data": None,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request validation failed.",
                    "detail": {"fields": fields},
                    "request_id": new_id("req"),
                },
            },
        )

    @application.get("/healthz", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/readyz", include_in_schema=False)
    async def ready(current: AppContainer = Depends(get_container)) -> dict[str, Any]:
        return {
            "status": "ready",
            "agent_mode": current.settings.agent_mode,
            "live_agent_ready": current.settings.live_agent_ready,
        }

    @application.post("/api/v1/sessions", status_code=201)
    async def create_session(current: AppContainer = Depends(get_container)) -> dict[str, Any]:
        session, token = current.repository.create_session(current.settings.session_ttl_seconds)
        return success(
            {
                "access_token": token,
                "expires_at": session.expires_at,
                "limits": {
                    "max_projects": session.max_projects,
                    "max_live_audits": session.max_live_audits,
                },
            }
        )

    @application.get("/api/v1/benchmarks")
    async def list_benchmarks(
        _: Session = Depends(get_session), current: AppContainer = Depends(get_container)
    ) -> dict[str, Any]:
        return success([item.model_dump(mode="json") for item in current.benchmarks.definitions()])

    @application.post("/api/v1/projects/from-benchmark", status_code=201)
    async def project_from_benchmark(
        body: BenchmarkProjectRequest,
        session: Session = Depends(get_session),
        current: AppContainer = Depends(get_container),
    ) -> dict[str, Any]:
        project = current.projects.create_benchmark_project(session, body.benchmark_id)
        return success(project_payload(project, current))

    @application.post("/api/v1/projects", status_code=201)
    async def create_project_endpoint(
        body: CreateProjectRequest,
        session: Session = Depends(get_session),
        current: AppContainer = Depends(get_container),
    ) -> dict[str, Any]:
        if body.source.type == SourceType.UPLOAD.value:
            project = current.projects.create_upload_project(session, body.name)
        else:
            if body.source.repository_url is None:
                raise PolygraphError("INVALID_REPOSITORY", "repository_url is required.")
            project = await current.projects.create_github_project(
                session, body.name, str(body.source.repository_url), body.source.ref
            )
        return success(project_payload(project, current))

    @application.post("/api/v1/projects/{project_id}/artifacts/presign")
    async def presign_artifacts(
        body: PresignRequest,
        project: Project = Depends(owned_project),
        current: AppContainer = Depends(get_container),
    ) -> dict[str, Any]:
        declared = current.projects.declare_uploads(
            project,
            [
                UploadDeclaration(
                    client_id=item.client_id,
                    filename=item.filename,
                    kind=item.kind,
                    size_bytes=item.size_bytes,
                    sha256=item.sha256,
                    media_type=item.media_type,
                )
                for item in body.artifacts
            ],
        )
        return success(
            {
                "uploads": [
                    {
                        "artifact_id": artifact.artifact_id,
                        "client_id": artifact.client_id,
                        "method": "PUT",
                        "url": url,
                        "headers": headers,
                    }
                    for artifact, url, headers in declared
                ]
            }
        )

    @application.put(
        "/api/v1/projects/{project_id}/artifacts/{artifact_id}/content", status_code=204
    )
    async def upload_artifact_content(
        artifact_id: str,
        request: Request,
        project: Project = Depends(owned_project),
        current: AppContainer = Depends(get_container),
    ) -> Response:
        artifact = current.repository.get(Artifact, artifact_id)
        if artifact is None or artifact.project_id != project.project_id:
            raise PolygraphError("INVALID_ARTIFACT", "Artifact was not found.", 404)
        content = await read_bounded_upload(
            request,
            declared_size=artifact.size_bytes,
            maximum_size=current.settings.max_artifact_bytes,
        )
        current.projects.upload_content(project, artifact, content)
        return Response(status_code=204)

    @application.post("/api/v1/projects/{project_id}/artifacts/complete")
    async def complete_artifacts(
        body: CompleteUploadsRequest,
        project: Project = Depends(owned_project),
        current: AppContainer = Depends(get_container),
    ) -> dict[str, Any]:
        updated = current.projects.complete_uploads(project, body.artifact_ids)
        return success(project_payload(updated, current))

    @application.get("/api/v1/projects/{project_id}")
    async def get_project_endpoint(
        project: Project = Depends(owned_project),
        current: AppContainer = Depends(get_container),
    ) -> dict[str, Any]:
        return success(project_payload(project, current))

    @application.patch("/api/v1/projects/{project_id}/mapping")
    async def update_mapping(
        body: MappingRequest,
        project: Project = Depends(owned_project),
        current: AppContainer = Depends(get_container),
    ) -> dict[str, Any]:
        updated = current.projects.update_mapping(project, body)
        return success(project_payload(updated, current))

    @application.put("/api/v1/projects/{project_id}/scenario")
    async def update_scenario(
        body: ScenarioRequest,
        project: Project = Depends(owned_project),
        current: AppContainer = Depends(get_container),
    ) -> dict[str, Any]:
        updated = current.projects.add_scenario(project, body)
        return success(project_payload(updated, current))

    @application.post("/api/v1/audits", status_code=202)
    async def start_audit(
        body: StartAuditRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8)],
        session: Session = Depends(get_session),
        current: AppContainer = Depends(get_container),
    ) -> dict[str, Any]:
        project = current.repository.get(Project, body.project_id)
        if project is None or project.session_id != session.session_id:
            raise PolygraphError("PROJECT_NOT_FOUND", "Project was not found.", 404)
        audit = current.audits.start(
            session, project, body.scenario_revision, body.mode, idempotency_key
        )
        return success(audit_payload(audit, current))

    @application.get("/api/v1/audits/{audit_id}")
    async def get_audit_endpoint(
        audit: Audit = Depends(owned_audit),
        current: AppContainer = Depends(get_container),
    ) -> dict[str, Any]:
        return success(audit_payload(audit, current))

    @application.get("/api/v1/audits/{audit_id}/events")
    async def audit_events(
        request: Request,
        audit: Audit = Depends(owned_audit),
        current: AppContainer = Depends(get_container),
        after_sequence: int = Query(default=0, ge=0),
        last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    ) -> Response:
        if last_event_id:
            resumed_sequence = current.repository.event_sequence(audit.audit_id, last_event_id)
            if resumed_sequence is not None:
                after_sequence = max(after_sequence, resumed_sequence)
        if "application/json" in request.headers.get("accept", ""):
            events = current.repository.list_events(audit.audit_id, after_sequence)
            return JSONResponse(success([event.model_dump(mode="json") for event in events]))

        async def stream() -> AsyncIterator[str]:
            cursor = after_sequence
            while True:
                events = current.repository.list_events(audit.audit_id, cursor)
                for event in events:
                    cursor = event.sequence
                    data = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
                    yield f"id: {event.event_id}\nevent: {event.type.value}\ndata: {data}\n\n"
                latest = current.repository.get(Audit, audit.audit_id)
                if latest is None or (
                    latest.status
                    in {
                        AuditStatus.COMPLETE,
                        AuditStatus.FAILED,
                        AuditStatus.FAILED_PARTIAL,
                        AuditStatus.WAITING_FOR_USER,
                    }
                    and cursor >= latest.last_event_sequence
                ):
                    return
                if await request.is_disconnected():
                    return
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @application.post("/api/v1/audits/{audit_id}/answers", status_code=202)
    async def answer_question(
        body: AnswerRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8)],
        audit: Audit = Depends(owned_audit),
        session: Session = Depends(get_session),
        current: AppContainer = Depends(get_container),
    ) -> dict[str, Any]:
        question = current.repository.get(Question, body.question_id)
        if question is None:
            raise PolygraphError("QUESTION_NOT_FOUND", "Question was not found.", 404)
        updated = current.audits.answer(session, audit, question, body.answer, idempotency_key)
        return success(audit_payload(updated, current))

    @application.post("/api/v1/audits/{audit_id}/report")
    async def create_report(
        body: ReportRequest,
        audit: Audit = Depends(owned_audit),
        current: AppContainer = Depends(get_container),
    ) -> dict[str, Any]:
        project = current.repository.get(Project, audit.project_id)
        if project is None:
            raise PolygraphError("PROJECT_NOT_FOUND", "Project was not found.", 404)
        report = current.audits.create_report(audit, project, body.audience)
        return success(report.model_dump(mode="json"))

    @application.delete("/api/v1/projects/{project_id}", status_code=204)
    async def delete_project(
        project: Project = Depends(owned_project),
        current: AppContainer = Depends(get_container),
    ) -> Response:
        current.artifacts.delete_project(project.project_id)
        current.repository.delete_project(project.project_id)
        return Response(status_code=204)

    return application


def project_payload(project: Project, container: AppContainer) -> dict[str, Any]:
    artifacts = [
        artifact.model_dump(mode="json")
        for artifact_id in project.artifact_ids
        if (artifact := container.repository.get(Artifact, artifact_id)) is not None
    ]
    return {**project.model_dump(mode="json"), "artifacts": artifacts}


def audit_payload(audit: Audit, container: AppContainer) -> dict[str, Any]:
    findings = [
        finding.model_dump(mode="json")
        for finding_id in audit.finding_ids
        if (finding := container.repository.get(Finding, finding_id)) is not None
    ]
    questions = [
        question.model_dump(mode="json")
        for question_id in audit.question_ids
        if (question := container.repository.get(Question, question_id)) is not None
    ]
    return {
        **audit.model_dump(mode="json"),
        "findings": findings,
        "open_questions": [question for question in questions if question["status"] == "open"],
        "events_url": f"/api/v1/audits/{audit.audit_id}/events",
    }


app = create_app()


def run() -> None:
    uvicorn.run("polygraphml.api.main:app", host="0.0.0.0", port=8000, reload=False)
