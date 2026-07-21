from __future__ import annotations

import hashlib

import pytest

from polygraphml.adapters.manifests import load_manifest_bytes, validate_manifest_path
from polygraphml.domain.models import ArtifactKind
from polygraphml.errors import PolygraphError


def _manifest() -> bytes:
    paths = {
        "dataset": "artifacts/evaluation.csv",
        "model": "artifacts/model.skops",
        "notebook": "analysis/evaluation.ipynb",
    }
    hashes = {path: hashlib.sha256(path.encode()).hexdigest() for path in paths.values()}
    lines = [
        'schema_version: "1"',
        "artifacts:",
        *[f"  {kind}: {path}" for kind, path in paths.items()],
        "mapping:",
        "  target_column: subscribed",
        "  split_column: split",
        "  reported_metric_location: 'cell:12'",
        "scenario:",
        "  revision: 1",
        "  target_definition: Whether the customer subscribes",
        "  row_entity: One marketing contact",
        "  decision_time: Before the current call begins",
        "  prediction_horizon: Current campaign response",
        "  split_unit: Customer",
        "  intended_metric: roc_auc",
        "features:",
        "  duration:",
        "    description: Duration of the current call",
        "    source_refs:",
        "      - https://example.test/dictionary#duration",
        "provenance:",
        "  dataset_source_url: https://example.test/dataset",
        "  license_name: CC BY 4.0",
        "  artifact_hashes:",
        *[f"    {path}: {digest}" for path, digest in hashes.items()],
    ]
    return ("\n".join(lines) + "\n").encode()


def test_manifest_parses_required_artifacts_mapping_and_context() -> None:
    manifest = load_manifest_bytes(_manifest())

    assert manifest.artifacts[ArtifactKind.MODEL] == "artifacts/model.skops"
    assert manifest.mapping.reported_metric_location == "cell:12"
    assert manifest.scenario.decision_time == "Before the current call begins"
    assert manifest.features["duration"].description == "Duration of the current call"


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/absolute/model.skops",
        "../model.skops",
        "a/../model.skops",
        "a//model.skops",
        "a\\model.skops",
    ],
)
def test_manifest_path_rejects_ambiguous_or_escaping_paths(path: str) -> None:
    with pytest.raises(ValueError):
        validate_manifest_path(path)


def test_manifest_rejects_missing_hash_or_answer_encoding() -> None:
    content = _manifest().replace(b"    artifacts/model.skops: ", b"    undeclared/result.txt: ", 1)
    with pytest.raises(PolygraphError, match="manifest is invalid"):
        load_manifest_bytes(content)


def test_manifest_rejects_unknown_fields_and_oversize() -> None:
    with pytest.raises(PolygraphError, match="manifest is invalid"):
        load_manifest_bytes(_manifest() + b"expected_finding: post_outcome\n")
    with pytest.raises(PolygraphError, match="exceeds 256 KiB"):
        load_manifest_bytes(b"x" * (256 * 1024 + 1))
