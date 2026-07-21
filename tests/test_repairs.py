from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_notebook

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
