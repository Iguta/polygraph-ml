from __future__ import annotations

import hashlib
from pathlib import Path

import nbformat
import pandas as pd
import pytest
from nbformat.v4 import new_code_cell, new_notebook, new_output

from polygraphml.adapters.datasets import TabularDatasetAdapter
from polygraphml.adapters.notebooks import NotebookInspector
from polygraphml.errors import PolygraphError


def test_csv_and_parquet_emit_canonical_profiles(tmp_path: Path) -> None:
    frame = pd.DataFrame({"feature": [1, 2, 3], "target": [0, 1, 1]})
    adapter = TabularDatasetAdapter()
    for suffix in ("csv", "parquet"):
        path = tmp_path / f"data.{suffix}"
        if suffix == "csv":
            frame.to_csv(path, index=False)
        else:
            frame.to_parquet(path, index=False)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        profile = adapter.profile(path, f"art_{suffix}", digest, "target")
        assert profile.row_count == 3
        assert profile.column_count == 2
        assert profile.target_balance == {"1": pytest.approx(2 / 3), "0": pytest.approx(1 / 3)}


def test_dataset_adapter_rejects_empty_or_unsupported(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("a,b\n")
    with pytest.raises(PolygraphError):
        TabularDatasetAdapter().load(empty)
    unsupported = tmp_path / "data.txt"
    unsupported.write_text("a,b\n1,2\n")
    with pytest.raises(PolygraphError, match="Unsupported"):
        TabularDatasetAdapter().load(unsupported)


def test_notebook_parser_finds_evidence_and_printed_claim(tmp_path: Path) -> None:
    path = tmp_path / "analysis.ipynb"
    notebook = new_notebook(
        cells=[
            new_code_cell("import pandas as pd\ndf = pd.read_csv('data.csv')"),
            new_code_cell(
                "from sklearn.preprocessing import StandardScaler\nX = StandardScaler().fit_transform(df[['x']])"
            ),
            new_code_cell(
                "from sklearn.model_selection import train_test_split\nX_train, X_test = train_test_split(X)"
            ),
            new_code_cell("model.fit(X_train, y_train)"),
            new_code_cell(
                "score = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])",
                outputs=[new_output(output_type="stream", name="stdout", text="AUC: 0.812\n")],
            ),
        ]
    )
    nbformat.write(notebook, path)
    result = NotebookInspector().inspect(path)
    assert result.data_read_cells == ["analysis.ipynb#cell=0"]
    assert result.preprocessing_before_split is True
    assert result.training_cells
    assert result.metric_cells
    assert result.claims[0].metric == "roc_auc"
    assert result.claims[0].value == pytest.approx(0.812)
