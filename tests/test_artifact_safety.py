from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import skops.io as skops_io
from sklearn.linear_model import LogisticRegression

from polygraphml.adapters.models import SkopsModelAdapter, XGBoostModelInspector
from polygraphml.config import Settings
from polygraphml.domain.models import ArtifactKind
from polygraphml.errors import PolygraphError
from polygraphml.storage.artifacts import (
    LocalArtifactStore,
    UploadDeclaration,
    validate_archive_member,
    validate_declaration,
    validate_filename,
)


@pytest.mark.parametrize("filename", ["model.pkl", "model.pickle", "model.joblib", "x.dill"])
def test_pickle_family_is_rejected(filename: str) -> None:
    with pytest.raises(PolygraphError, match="Pickle-family") as error:
        validate_filename(filename, ArtifactKind.MODEL)
    assert error.value.code == "UNSAFE_ARTIFACT"


@pytest.mark.parametrize("filename", ["../data.csv", "/outside/data.csv", r"..\data.csv"])
def test_upload_path_traversal_is_rejected(filename: str) -> None:
    with pytest.raises(PolygraphError):
        validate_filename(filename, ArtifactKind.DATASET)


@pytest.mark.parametrize(
    ("path", "is_symlink", "is_device"),
    [("../escape", False, False), ("safe/link", True, False), ("safe/dev", False, True)],
)
def test_unsafe_archive_members_are_rejected(path: str, is_symlink: bool, is_device: bool) -> None:
    with pytest.raises(PolygraphError):
        validate_archive_member(path, is_symlink=is_symlink, is_device=is_device)


def test_archive_upload_is_rejected_before_any_expansion() -> None:
    with pytest.raises(PolygraphError, match="not supported"):
        validate_filename("evidence.zip", ArtifactKind.DATASET)


def test_declaration_and_store_verify_checksum(tmp_path: Path) -> None:
    content = b"a,b\n1,2\n"
    digest = hashlib.sha256(content).hexdigest()
    declaration = UploadDeclaration(
        client_id="data",
        filename="data.csv",
        kind=ArtifactKind.DATASET,
        size_bytes=len(content),
        sha256=digest,
        media_type="text/csv",
    )
    settings = Settings(
        environment="test",
        database_path=tmp_path / "db",
        artifact_root=tmp_path / "artifacts",
    )
    validate_declaration(declaration, settings)
    store = LocalArtifactStore(settings.artifact_root)
    key = store.key("prj_1", declaration.client_id, declaration.filename)
    store.write(key, content, settings.max_artifact_bytes)
    assert store.verify(key, len(content), digest).read_bytes() == content
    with pytest.raises(PolygraphError, match="does not match"):
        store.verify(key, len(content), "0" * 64)


def test_skops_allowlisted_estimator_and_non_estimator(tmp_path: Path) -> None:
    model_path = tmp_path / "model.skops"
    model = LogisticRegression().fit([[0.0], [1.0]], [0, 1])
    skops_io.dump(model, model_path)
    loaded = SkopsModelAdapter().load(model_path)
    assert type(loaded).__module__.startswith("sklearn.")

    invalid_path = tmp_path / "mapping.skops"
    skops_io.dump({"not": "an estimator"}, invalid_path)
    with pytest.raises(PolygraphError, match="not a supported estimator"):
        SkopsModelAdapter().load(invalid_path)


def test_arbitrary_json_is_not_accepted_as_xgboost(tmp_path: Path) -> None:
    path = tmp_path / "model.json"
    path.write_text('{"weights": [1, 2]}')
    with pytest.raises(PolygraphError, match="Arbitrary JSON"):
        XGBoostModelInspector().inspect_json(path)

    path.write_text("not-json")
    with pytest.raises(PolygraphError, match="malformed"):
        XGBoostModelInspector().inspect_json(path)

    path.write_text('{"learner": {}, "version": [3, 0, 0]}')
    assert XGBoostModelInspector().inspect_json(path)["version"] == [3, 0, 0]
