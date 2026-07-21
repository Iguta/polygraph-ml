from __future__ import annotations

import ast
import difflib
import hashlib
import io
import json
import zipfile
from pathlib import Path

import nbformat

from polygraphml.domain.ids import new_id
from polygraphml.domain.models import (
    Artifact,
    ArtifactKind,
    Audit,
    AuditStatus,
    Correction,
    Project,
    RepairBundle,
)
from polygraphml.errors import PolygraphError
from polygraphml.storage.artifacts import ArtifactStore
from polygraphml.storage.base import DomainRepository


class RepairService:
    def __init__(
        self,
        repository: DomainRepository,
        artifacts: ArtifactStore,
        max_bundle_bytes: int,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.max_bundle_bytes = max_bundle_bytes

    def create(self, audit: Audit, project: Project) -> RepairBundle:
        existing = next(
            iter(self.repository.list(RepairBundle, audit.audit_id)),
            None,
        )
        if existing is not None:
            return existing
        if audit.status != AuditStatus.COMPLETE:
            raise PolygraphError(
                "AUDIT_IN_PROGRESS", "Repair bundle requires a completed audit.", status_code=409
            )
        corrections = [
            correction
            for correction_id in audit.correction_ids
            if (correction := self.repository.get(Correction, correction_id)) is not None
        ]
        removed_features = sorted(
            {feature for correction in corrections for feature in correction.features_removed}
        )
        if not removed_features or audit.metric_comparison is None:
            return self._unavailable(
                audit,
                project,
                "No deterministic feature-removal correction is available for this audit.",
            )
        notebook = self._notebook(project)
        patch = self._literal_feature_patch(notebook, removed_features)
        if patch is None:
            return self._unavailable(
                audit,
                project,
                "The notebook has no unique literal feature list that can be patched safely.",
            )
        files = self._bundle_files(audit, project, corrections, removed_features, patch)
        archive = self._zip(files)
        if len(archive) > self.max_bundle_bytes:
            return self._unavailable(
                audit, project, "The generated repair bundle exceeds the artifact size limit."
            )
        bundle_id = new_id("rpb")
        storage_key = f"{project.project_id}/repairs/{audit.audit_id}/{bundle_id}.zip"
        size, digest = self.artifacts.write(storage_key, archive, self.max_bundle_bytes)
        bundle = RepairBundle(
            bundle_id=bundle_id,
            audit_id=audit.audit_id,
            project_id=project.project_id,
            status="available",
            sha256=digest,
            size_bytes=size,
            storage_key=storage_key,
            file_hashes={
                name: hashlib.sha256(content).hexdigest() for name, content in files.items()
            },
            limitations=[
                "The patch edits only a unique literal features assignment; it does not execute "
                "the submitted notebook."
            ],
        )
        return self.repository.put(bundle)

    def download_url(self, bundle: RepairBundle) -> str | None:
        if bundle.status != "available" or bundle.storage_key is None:
            return None
        return self.artifacts.presign_get(bundle.storage_key) or (
            f"/api/v1/audits/{bundle.audit_id}/repair-bundle/{bundle.bundle_id}/download"
        )

    def _notebook(self, project: Project) -> Path:
        artifact = next(
            (
                item
                for artifact_id in project.artifact_ids
                if (item := self.repository.get(Artifact, artifact_id)) is not None
                and item.kind == ArtifactKind.NOTEBOOK
            ),
            None,
        )
        if artifact is None:
            raise PolygraphError("MAPPING_INCOMPLETE", "A notebook artifact is required.")
        return self.artifacts.path_for_key(artifact.storage_key)

    @staticmethod
    def _literal_feature_patch(notebook_path: Path, removed_features: list[str]) -> str | None:
        try:
            notebook = nbformat.read(notebook_path, as_version=4)  # type: ignore[no-untyped-call]
        except Exception as exc:
            raise PolygraphError("INVALID_ARTIFACT", "Notebook could not be parsed.") from exc
        candidates: list[tuple[int, str, str]] = []
        for cell_index, cell in enumerate(notebook.cells):
            if cell.cell_type != "code":
                continue
            source = str(cell.source)
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                    continue
                target = node.targets[0]
                if not isinstance(target, ast.Name) or target.id != "features":
                    continue
                if not isinstance(node.value, (ast.List, ast.Tuple)):
                    continue
                values = [
                    item.value
                    for item in node.value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                ]
                if len(values) != len(node.value.elts) or not set(removed_features).issubset(
                    values
                ):
                    continue
                kept = [value for value in values if value not in set(removed_features)]
                if not kept:
                    continue
                lines = source.splitlines(keepends=True)
                start = node.lineno - 1
                end = node.end_lineno or node.lineno
                indentation = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
                replacement = f"{indentation}features = {kept!r}\n"
                modified = "".join([*lines[:start], replacement, *lines[end:]])
                candidates.append((cell_index, source, modified))
        if len(candidates) != 1:
            return None
        cell_index, original, modified = candidates[0]
        return "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                modified.splitlines(keepends=True),
                fromfile=f"{notebook_path.name}#cell={cell_index}",
                tofile=f"{notebook_path.name}#cell={cell_index}",
            )
        )

    @staticmethod
    def _bundle_files(
        audit: Audit,
        project: Project,
        corrections: list[Correction],
        removed_features: list[str],
        patch: str,
    ) -> dict[str, bytes]:
        comparison = audit.metric_comparison
        correction_payload = {
            "schema_version": "1",
            "audit_id": audit.audit_id,
            "removed_features": removed_features,
            "corrections": [item.model_dump(mode="json") for item in corrections],
            "metric_comparison": comparison.model_dump(mode="json") if comparison else None,
        }
        protocol_payload = {
            "schema_version": "1",
            "scenario_revision": audit.scenario_revision,
            "scenario": (project.scenarios[audit.scenario_revision - 1].model_dump(mode="json")),
            "mapping": project.mapping.model_dump(mode="json"),
            "artifact_hashes": audit.provenance.artifact_hashes,
            "source_commit": audit.provenance.source_commit,
            "feature_order": audit.provenance.feature_order,
            "evaluator_version": audit.provenance.evaluator_version,
        }
        readme = (
            "# PolygraphML deterministic repair bundle\n\n"
            f"Audit: `{audit.audit_id}`\n\n"
            f"Removed features: `{', '.join(removed_features)}`\n\n"
            "Apply `feature-list.patch` manually, rerun the original training and evaluation "
            "environment, and compare the result with `correction.json`. The patch was generated "
            "only because one unambiguous literal `features` assignment contained every removed "
            "feature. Submitted notebook code was not executed. Review the patch before applying it.\n"
        )
        return {
            "README.md": readme.encode(),
            "correction.json": (
                json.dumps(correction_payload, indent=2, sort_keys=True) + "\n"
            ).encode(),
            "feature-list.patch": patch.encode(),
            "protocol.json": (
                json.dumps(protocol_payload, indent=2, sort_keys=True) + "\n"
            ).encode(),
        }

    @staticmethod
    def _zip(files: dict[str, bytes]) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(files):
                information = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                information.compress_type = zipfile.ZIP_DEFLATED
                information.external_attr = 0o644 << 16
                archive.writestr(information, files[name])
        return output.getvalue()

    def _unavailable(self, audit: Audit, project: Project, reason: str) -> RepairBundle:
        return self.repository.put(
            RepairBundle(
                bundle_id=new_id("rpb"),
                audit_id=audit.audit_id,
                project_id=project.project_id,
                status="unavailable",
                limitations=[reason],
            )
        )
