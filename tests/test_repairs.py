from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import nbformat
import pytest
from nbformat.v4 import new_code_cell, new_notebook

from polygraphml.domain.models import (
    AdapterStatus,
    Artifact,
    ArtifactKind,
    ArtifactMapping,
    Project,
    ProjectSource,
    ProjectStatus,
    SourceType,
)
from polygraphml.errors import PolygraphError
from polygraphml.services.repairs import RepairService


def _notebook(path: Path, source: str) -> Path:
    nbformat.write(new_notebook(cells=[new_code_cell(source)]), path)
    return path


def test_literal_feature_patch_is_exact_and_removes_only_confirmed_feature(
    tmp_path: Path,
) -> None:
    path = _notebook(
        tmp_path / "training.ipynb",
        "features = ['safe', 'leak', 'other']\nmodel.fit(df[features], y)\n",
    )

    patch = RepairService._literal_feature_patch(path, ["leak"])

    assert patch is not None
    assert "-features = ['safe', 'leak', 'other']" in patch
    assert "+features = ['safe', 'other']" in patch


def test_literal_feature_patch_refuses_dynamic_or_ambiguous_lists(tmp_path: Path) -> None:
    dynamic = _notebook(tmp_path / "dynamic.ipynb", "features = base_features + ['leak']\n")
    assert RepairService._literal_feature_patch(dynamic, ["leak"]) is None

    ambiguous = _notebook(
        tmp_path / "ambiguous.ipynb",
        "features = ['safe', 'leak']\nfeatures = ['other', 'leak']\n",
    )
    assert RepairService._literal_feature_patch(ambiguous, ["leak"]) is None


def test_repair_uses_the_explicitly_mapped_notebook(tmp_path: Path) -> None:
    first = Artifact(
        artifact_id="art_first",
        project_id="prj_1",
        kind=ArtifactKind.NOTEBOOK,
        filename="first.ipynb",
        sha256="a" * 64,
        size_bytes=10,
        media_type="application/x-ipynb+json",
        storage_key="prj_1/first.ipynb",
        adapter="ipynb-static",
        adapter_status=AdapterStatus.SUPPORTED,
    )
    mapped = first.model_copy(
        update={
            "artifact_id": "art_mapped",
            "filename": "mapped.ipynb",
            "storage_key": "prj_1/mapped.ipynb",
        }
    )
    project = Project(
        project_id="prj_1",
        session_id="ses_1",
        name="Mapped notebook",
        source=ProjectSource(type=SourceType.UPLOAD),
        status=ProjectStatus.READY,
        artifact_ids=[first.artifact_id, mapped.artifact_id],
        mapping=ArtifactMapping(notebook_artifact_id=mapped.artifact_id),
    )
    repository = Mock()
    repository.get.return_value = mapped
    artifacts = Mock()
    artifacts.path_for_key.return_value = tmp_path / "mapped.ipynb"
    service = RepairService(repository, artifacts, 1024)

    assert service._notebook(project) == tmp_path / "mapped.ipynb"
    repository.get.assert_called_once_with(Artifact, mapped.artifact_id)
    artifacts.path_for_key.assert_called_once_with(mapped.storage_key)


def test_repair_rejects_a_mapped_notebook_from_another_project(tmp_path: Path) -> None:
    artifact = Artifact(
        artifact_id="art_foreign",
        project_id="prj_other",
        kind=ArtifactKind.NOTEBOOK,
        filename="foreign.ipynb",
        sha256="b" * 64,
        size_bytes=10,
        media_type="application/x-ipynb+json",
        storage_key="prj_other/foreign.ipynb",
        adapter="ipynb-static",
        adapter_status=AdapterStatus.SUPPORTED,
    )
    project = Project(
        project_id="prj_1",
        session_id="ses_1",
        name="Invalid mapping",
        source=ProjectSource(type=SourceType.UPLOAD),
        status=ProjectStatus.READY,
        artifact_ids=[artifact.artifact_id],
        mapping=ArtifactMapping(notebook_artifact_id=artifact.artifact_id),
    )
    repository = Mock()
    repository.get.return_value = artifact
    service = RepairService(repository, Mock(), 1024)

    with pytest.raises(PolygraphError, match="valid mapped notebook"):
        service._notebook(project)
