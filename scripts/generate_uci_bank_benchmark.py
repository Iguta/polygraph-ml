from __future__ import annotations

import argparse
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd
import skops.io as skops_io
import yaml
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook, new_output
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SOURCE_URL = "https://archive.ics.uci.edu/static/public/222/bank+marketing.zip"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/222/bank%2Bmarketing"
SOURCE_DOI = "https://doi.org/10.24432/C5K306"
OUTER_ZIP_SHA256 = "e0bf5f5de5b846e2f18e9d90606637267d46dfa260e0f17bb12e605db5efbeb4"
INNER_ZIP_SHA256 = "99d7e8eb12401ed278b793984423915411ea8df099e1795f9fefe254f513fe5e"
SOURCE_CSV_SHA256 = "d1513ec63b385506f7cfce9f2c5caa9fe99e7ba4e8c3fa264b3aaf0f849ed32d"
FEATURES = [
    "age",
    "job",
    "marital",
    "education",
    "default",
    "balance",
    "housing",
    "loan",
    "contact",
    "day",
    "month",
    "duration",
    "campaign",
    "pdays",
    "previous",
    "poutcome",
]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read_source(source_zip: Path | None) -> bytes:
    if source_zip is not None:
        outer = source_zip.read_bytes()
    else:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:  # noqa: S310
            outer = response.read(2 * 1024 * 1024)
    if _sha256(outer) != OUTER_ZIP_SHA256:
        raise RuntimeError("UCI outer archive does not match its pinned SHA-256.")
    with zipfile.ZipFile(io.BytesIO(outer)) as archive:
        inner = archive.read("bank.zip")
    if _sha256(inner) != INNER_ZIP_SHA256:
        raise RuntimeError("UCI nested archive does not match its pinned SHA-256.")
    with zipfile.ZipFile(io.BytesIO(inner)) as archive:
        source = archive.read("bank-full.csv")
    if _sha256(source) != SOURCE_CSV_SHA256:
        raise RuntimeError("UCI source CSV does not match its pinned SHA-256.")
    return source


def _model_ready_frame(source: bytes) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    original = pd.read_csv(io.BytesIO(source), sep=";")
    encoded = pd.DataFrame(index=original.index)
    categories: dict[str, dict[str, int]] = {}
    for feature in FEATURES:
        if pd.api.types.is_numeric_dtype(original[feature]):
            encoded[feature] = original[feature]
            continue
        labels = sorted(str(value) for value in original[feature].unique())
        mapping = {label: index for index, label in enumerate(labels)}
        categories[feature] = mapping
        encoded[feature] = original[feature].astype(str).map(mapping).astype(int)
    encoded["subscribed"] = (original["y"] == "yes").astype(int)
    encoded.insert(0, "row_id", [f"UCI-BANK-{index:05d}" for index in range(len(encoded))])
    train_indices, test_indices = train_test_split(
        np.arange(len(encoded)),
        test_size=0.28,
        random_state=42,
        stratify=encoded["subscribed"],
    )
    encoded["split"] = "train"
    encoded.loc[test_indices, "split"] = "test"
    if len(train_indices) + len(test_indices) != len(encoded):
        raise RuntimeError("Deterministic split did not cover every row.")
    return encoded, categories


def generate(repository_root: Path, source_zip: Path | None = None) -> dict[str, object]:
    source = _read_source(source_zip)
    frame, categories = _model_ready_frame(source)
    train = frame["split"] == "train"
    test = frame["split"] == "test"
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, random_state=42)),
        ]
    )
    model.fit(frame.loc[train, FEATURES], frame.loc[train, "subscribed"])
    reported_auc = float(
        roc_auc_score(
            frame.loc[test, "subscribed"],
            model.predict_proba(frame.loc[test, FEATURES])[:, 1],
        )
    )

    benchmark_root = repository_root / "src" / "polygraphml" / "benchmarks" / "data" / "uci_bank"
    benchmark_root.mkdir(parents=True, exist_ok=True)
    dataset_path = benchmark_root / "bank_marketing_evaluation.csv"
    model_path = benchmark_root / "bank_marketing_model.skops"
    notebook_path = benchmark_root / "bank_marketing_evaluation.ipynb"
    metadata_path = benchmark_root / "derivation.txt"
    frame.to_csv(dataset_path, index=False)
    skops_io.dump(model, model_path)
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "source_url": SOURCE_URL,
                "source_page": SOURCE_PAGE,
                "source_doi": SOURCE_DOI,
                "outer_zip_sha256": OUTER_ZIP_SHA256,
                "inner_zip_sha256": INNER_ZIP_SHA256,
                "source_csv_sha256": SOURCE_CSV_SHA256,
                "category_encodings": categories,
                "split": {"test_fraction": 0.28, "random_seed": 42, "stratified": True},
                "row_count": len(frame),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    notebook = new_notebook(
        metadata={
            "polygraphml": {
                "source": SOURCE_DOI,
                "license": "CC BY 4.0",
                "derivation": "derivation.txt",
            }
        },
        cells=[
            new_markdown_cell(
                "# UCI Bank Marketing evaluation\n\n"
                "This notebook evaluates whether a client subscribes to a term deposit. "
                "The model-ready evaluation table and category mapping are reproducibly "
                "derived by `scripts/generate_uci_bank_benchmark.py`."
            ),
            new_code_cell(
                "import pandas as pd\n"
                "import skops.io as sio\n"
                "from sklearn.metrics import roc_auc_score\n"
                "df = pd.read_csv('bank_marketing_evaluation.csv')\n"
                "model = sio.load('bank_marketing_model.skops', trusted=[] )"
            ),
            new_code_cell(
                f"features = {FEATURES!r}\n"
                "test = df['split'] == 'test'\n"
                "probabilities = model.predict_proba(df.loc[test, features])[:, 1]"
            ),
            new_code_cell(
                "auc = roc_auc_score(df.loc[test, 'subscribed'], probabilities)\n"
                "print(f'ROC AUC: {auc:.6f}')",
                outputs=[
                    new_output(
                        output_type="stream",
                        name="stdout",
                        text=f"ROC AUC: {reported_auc:.6f}\n",
                    )
                ],
                execution_count=3,
            ),
        ],
    )
    nbformat.write(notebook, notebook_path)

    relative_artifacts = {
        "dataset": dataset_path.relative_to(repository_root).as_posix(),
        "model": model_path.relative_to(repository_root).as_posix(),
        "notebook": notebook_path.relative_to(repository_root).as_posix(),
        "source": metadata_path.relative_to(repository_root).as_posix(),
    }
    generator_path = repository_root / "scripts" / "generate_uci_bank_benchmark.py"
    hashes = {
        path: _sha256((repository_root / path).read_bytes()) for path in relative_artifacts.values()
    }
    manifest = {
        "schema_version": "1",
        "artifacts": relative_artifacts,
        "mapping": {
            "target_column": "subscribed",
            "split_column": "split",
            "entity_column": "row_id",
            "reported_metric_location": "bank_marketing_evaluation.ipynb#cell=3",
        },
        "scenario": {
            "revision": 1,
            "target_definition": "Whether the client subscribes to a term deposit",
            "row_entity": "One client contact in a direct-marketing campaign",
            "decision_time": "Before the current marketing call begins",
            "prediction_horizon": "Response to the current marketing contact",
            "split_unit": "row_id",
            "intended_metric": "roc_auc",
            "positive_label": "1",
            "notes": (
                "UCI Bank Marketing, DOI 10.24432/C5K306. The derived table preserves all "
                "45,211 records and uses deterministic category codes documented in derivation.txt."
            ),
        },
        "features": {
            "duration": {
                "description": "Duration in seconds of the current campaign's last contact",
                "source_refs": [f"{SOURCE_PAGE}#Additional-Variable-Information"],
            },
            "poutcome": {
                "description": "Outcome of the previous marketing campaign",
                "source_refs": [f"{SOURCE_PAGE}#Additional-Variable-Information"],
            },
        },
        "provenance": {
            "dataset_source_url": SOURCE_DOI,
            "license_name": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "artifact_hashes": hashes,
        },
    }
    manifest_path = repository_root / ".polygraphml.yml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return {
        "reported_auc": reported_auc,
        "row_count": len(frame),
        "manifest": str(manifest_path),
        "generator_sha256": _sha256(generator_path.read_bytes()),
        "artifacts": hashes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the pinned UCI Bank benchmark bundle.")
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-zip", type=Path)
    arguments = parser.parse_args()
    result = generate(arguments.repository_root.resolve(), arguments.source_zip)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
