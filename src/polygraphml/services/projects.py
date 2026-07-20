from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import HttpUrl

from polygraphml.adapters.models import SkopsModelAdapter, XGBoostModelInspector
from polygraphml.adapters.notebooks import NotebookInspector
from polygraphml.benchmarks.catalog import BenchmarkCatalog
from polygraphml.config import Settings
from polygraphml.domain.ids import new_id
from polygraphml.domain.models import (
    AdapterStatus,
    Artifact,
    ArtifactKind,
    ArtifactMapping,
    Project,
    ProjectSource,
    ProjectStatus,
    Scenario,
    Session,
    SourceType,
    utc_now,
)
from polygraphml.errors import PolygraphError
from polygraphml.storage.artifacts import (
    ALLOWED_SUFFIXES,
    ArtifactStore,
    UploadDeclaration,
    validate_declaration,
)
from polygraphml.storage.base import DomainRepository


def adapter_for(kind: ArtifactKind, filename: str) -> tuple[str, AdapterStatus]:
    suffix = Path(filename).suffix.lower()
    if kind == ArtifactKind.DATASET:
        return (suffix.removeprefix("."), AdapterStatus.SUPPORTED)
    if suffix == ".skops":
        return ("skops", AdapterStatus.SUPPORTED)
    if suffix in {".json", ".ubj"}:
        return ("xgboost", AdapterStatus.LIMITED)
    if suffix == ".onnx":
        return ("onnx", AdapterStatus.LIMITED)
    if kind == ArtifactKind.NOTEBOOK:
        return ("ipynb-static", AdapterStatus.SUPPORTED)
    if kind == ArtifactKind.MANIFEST:
        return ("polygraphml-yaml", AdapterStatus.SUPPORTED)
    return ("static-source", AdapterStatus.SUPPORTED)


class ProjectService:
    def __init__(
        self,
        settings: Settings,
        repository: DomainRepository,
        artifacts: ArtifactStore,
        benchmarks: BenchmarkCatalog,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.artifacts = artifacts
        self.benchmarks = benchmarks

    def create_upload_project(self, session: Session, name: str) -> Project:
        self._check_project_quota(session)
        project = Project(
            project_id=new_id("prj"),
            session_id=session.session_id,
            name=name,
            source=ProjectSource(type=SourceType.UPLOAD),
            status=ProjectStatus.READY_FOR_UPLOAD,
        )
        return self.repository.put(project)

    def create_benchmark_project(
        self,
        session: Session,
        benchmark_id: str,
    ) -> Project:
        self._check_project_quota(session)
        project_id = new_id("prj")
        project, artifacts = self.benchmarks.materialize(
            benchmark_id, project_id, session.session_id, self.artifacts
        )
        self.repository.put(project)
        for artifact in artifacts:
            self.repository.put(artifact)
        return project

    async def create_github_project(
        self,
        session: Session,
        name: str,
        repository_url: str,
        ref: str,
    ) -> Project:
        self._check_project_quota(session)
        owner, repository_name = self._parse_github_url(repository_url)
        project = Project(
            project_id=new_id("prj"),
            session_id=session.session_id,
            name=name,
            source=ProjectSource(
                type=SourceType.GITHUB,
                repository_url=HttpUrl(repository_url),
                requested_ref=ref,
            ),
            status=ProjectStatus.IMPORTING,
        )
        self.repository.put(project)
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "PolygraphML/0.1"}
        timeout = httpx.Timeout(20.0)
        async with httpx.AsyncClient(
            headers=headers, timeout=timeout, follow_redirects=False
        ) as client:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repository_name}/commits/{ref}"
            )
            if response.status_code != 200:
                project.status = ProjectStatus.REJECTED
                project.warnings.append("GitHub ref could not be resolved.")
                self.repository.put(project)
                raise PolygraphError(
                    "INVALID_REPOSITORY",
                    "The public GitHub repository or ref could not be resolved.",
                    detail={"github_status": response.status_code},
                )
            commit = str(response.json().get("sha", ""))
            if len(commit) != 40:
                raise PolygraphError("INVALID_REPOSITORY", "GitHub returned an invalid commit SHA.")
            tree_response = await client.get(
                f"https://api.github.com/repos/{owner}/{repository_name}/git/trees/{commit}",
                params={"recursive": "1"},
            )
            if tree_response.status_code != 200:
                raise PolygraphError(
                    "INVALID_REPOSITORY", "Repository tree could not be inspected."
                )
            tree = tree_response.json().get("tree", [])
            candidates = [
                item
                for item in tree
                if item.get("type") == "blob"
                and self._kind_for_path(str(item.get("path", ""))) is not None
                and int(item.get("size") or 0) <= self.settings.max_artifact_bytes
            ][:20]
            for item in candidates:
                source_path = str(item["path"])
                kind = self._kind_for_path(source_path)
                if kind is None:
                    continue
                raw = await client.get(
                    f"https://raw.githubusercontent.com/{owner}/{repository_name}/{commit}/{source_path}"
                )
                if raw.status_code != 200 or not raw.content:
                    project.warnings.append(f"Could not import {source_path}.")
                    continue
                filename = Path(source_path).name
                client_id = hashlib.sha256(source_path.encode()).hexdigest()[:16]
                storage_key = self.artifacts.key(project.project_id, client_id, filename)
                size, sha256 = self.artifacts.write(
                    storage_key, raw.content, self.settings.max_artifact_bytes
                )
                adapter, status = adapter_for(kind, filename)
                artifact = Artifact(
                    artifact_id=new_id("art"),
                    project_id=project.project_id,
                    kind=kind,
                    filename=filename,
                    sha256=sha256,
                    size_bytes=size,
                    media_type="application/octet-stream",
                    storage_key=storage_key,
                    adapter=adapter,
                    adapter_status=status,
                    source_ref=f"github:{source_path}@{commit}",
                )
                self._inspect_supported_artifact(artifact)
                self.repository.put(artifact)
                project.artifact_ids.append(artifact.artifact_id)

        project.source.resolved_commit = commit
        project.status = ProjectStatus.READY_FOR_MAPPING
        if not project.artifact_ids:
            project.warnings.append(
                "No supported model, data, notebook, or manifest artifacts were found."
            )
        project.updated_at = utc_now()
        return self.repository.put(project)

    def declare_uploads(
        self,
        project: Project,
        declarations: list[UploadDeclaration],
    ) -> list[tuple[Artifact, str, dict[str, str]]]:
        if project.status not in {
            ProjectStatus.READY_FOR_UPLOAD,
            ProjectStatus.READY_FOR_MAPPING,
        }:
            raise PolygraphError("INVALID_REQUEST", "Project is not accepting uploads.")
        if len(declarations) > 12:
            raise PolygraphError("INVALID_REQUEST", "At most 12 artifacts may be declared at once.")
        results: list[tuple[Artifact, str, dict[str, str]]] = []
        seen_client_ids: set[str] = set()
        for declaration in declarations:
            validate_declaration(declaration, self.settings)
            if declaration.client_id in seen_client_ids:
                raise PolygraphError("INVALID_REQUEST", "Duplicate client_id in upload request.")
            seen_client_ids.add(declaration.client_id)
            storage_key = self.artifacts.key(
                project.project_id, declaration.client_id, declaration.filename
            )
            adapter, status = adapter_for(declaration.kind, declaration.filename)
            artifact = Artifact(
                artifact_id=new_id("art"),
                project_id=project.project_id,
                kind=declaration.kind,
                filename=declaration.filename,
                sha256=declaration.sha256,
                size_bytes=declaration.size_bytes,
                media_type=declaration.media_type,
                storage_key=storage_key,
                adapter=adapter,
                adapter_status=status,
                validation_notes=["Upload pending verification."],
                source_ref=f"upload:{declaration.client_id}",
                client_id=declaration.client_id,
                upload_status="pending",
            )
            self.repository.put(artifact)
            project.artifact_ids.append(artifact.artifact_id)
            presigned = self.artifacts.presign_put(
                storage_key, declaration.media_type, declaration.sha256
            )
            url, headers = presigned or (
                f"/api/v1/projects/{project.project_id}/artifacts/{artifact.artifact_id}/content",
                {"Content-Type": artifact.media_type},
            )
            results.append((artifact, url, headers))
        project.status = ProjectStatus.VALIDATING
        project.updated_at = utc_now()
        self.repository.put(project)
        return results

    def upload_content(self, project: Project, artifact: Artifact, content: bytes) -> Artifact:
        if artifact.project_id != project.project_id or artifact.upload_status != "pending":
            raise PolygraphError("INVALID_ARTIFACT", "Upload intent is not active.")
        self.artifacts.write(artifact.storage_key, content, self.settings.max_artifact_bytes)
        return artifact

    def complete_uploads(self, project: Project, artifact_ids: list[str]) -> Project:
        for artifact_id in artifact_ids:
            artifact = self.repository.get(Artifact, artifact_id)
            if artifact is None or artifact.project_id != project.project_id:
                raise PolygraphError(
                    "INVALID_ARTIFACT", "Artifact does not belong to this project."
                )
            self.artifacts.verify(artifact.storage_key, artifact.size_bytes, artifact.sha256)
            artifact.upload_status = "complete"
            artifact.validation_notes = []
            if self.settings.storage_backend == "local":
                self._inspect_supported_artifact(artifact)
            else:
                artifact.validation_notes.append(
                    "Content inspection is deferred to the isolated audit worker."
                )
            self.repository.put(artifact)
        project.status = ProjectStatus.READY_FOR_MAPPING
        project.updated_at = utc_now()
        return self.repository.put(project)

    def update_mapping(self, project: Project, mapping: ArtifactMapping) -> Project:
        selected = {
            value
            for value in (
                mapping.dataset_artifact_id,
                mapping.model_artifact_id,
                mapping.notebook_artifact_id,
            )
            if value is not None
        }
        if not selected.issubset(set(project.artifact_ids)):
            raise PolygraphError(
                "MAPPING_INCOMPLETE", "Mapped artifact does not belong to project."
            )
        artifacts = {
            artifact_id: self.repository.get(Artifact, artifact_id) for artifact_id in selected
        }
        if any(
            artifact is None or artifact.upload_status != "complete"
            for artifact in artifacts.values()
        ):
            raise PolygraphError("MAPPING_INCOMPLETE", "All mapped uploads must be complete.")
        project.mapping = mapping
        complete = all(
            (
                mapping.dataset_artifact_id,
                mapping.model_artifact_id,
                mapping.notebook_artifact_id,
                mapping.target_column,
                mapping.split_column,
            )
        )
        project.status = ProjectStatus.READY if complete else ProjectStatus.PREFLIGHT_ONLY
        project.updated_at = utc_now()
        return self.repository.put(project)

    def add_scenario(self, project: Project, scenario: Scenario) -> Project:
        revision = len(project.scenarios) + 1
        project.scenarios.append(
            scenario.model_copy(update={"revision": revision, "created_at": utc_now()})
        )
        project.updated_at = utc_now()
        return self.repository.put(project)

    def _inspect_supported_artifact(self, artifact: Artifact) -> None:
        path = self.artifacts.path_for_key(artifact.storage_key)
        if artifact.adapter == "skops":
            SkopsModelAdapter().inspect(path)
        elif artifact.adapter == "xgboost" and path.suffix.lower() == ".json":
            XGBoostModelInspector().inspect_json(path)
        elif artifact.adapter == "ipynb-static":
            NotebookInspector().inspect(path)

    def _check_project_quota(self, session: Session) -> None:
        if self.repository.count_projects(session.session_id) >= session.max_projects:
            raise PolygraphError("RATE_LIMITED", "Project quota has been reached.", status_code=429)

    @staticmethod
    def _parse_github_url(repository_url: str) -> tuple[str, str]:
        parsed = urlparse(repository_url)
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            raise PolygraphError(
                "INVALID_REPOSITORY", "Only public github.com HTTPS URLs are accepted."
            )
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(parts) != 2:
            raise PolygraphError(
                "INVALID_REPOSITORY", "Repository URL must contain owner and name."
            )
        owner, repository = parts
        return owner, repository.removesuffix(".git")

    @staticmethod
    def _kind_for_path(path: str) -> ArtifactKind | None:
        suffix = Path(path).suffix.lower()
        for kind, suffixes in ALLOWED_SUFFIXES.items():
            if suffix in suffixes:
                return kind
        return None
