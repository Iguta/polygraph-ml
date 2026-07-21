from __future__ import annotations

import json
import os
import resource
import sys
from pathlib import Path
from typing import Any


def _apply_limits() -> None:
    limits = (
        (resource.RLIMIT_CPU, "POLYGRAPHML_COMPUTE_CPU_SECONDS"),
        (resource.RLIMIT_AS, "POLYGRAPHML_COMPUTE_MEMORY_BYTES"),
        (resource.RLIMIT_NOFILE, "POLYGRAPHML_COMPUTE_NOFILE"),
        (resource.RLIMIT_FSIZE, "POLYGRAPHML_COMPUTE_FILE_BYTES"),
    )
    for resource_kind, environment_name in limits:
        value = int(os.environ[environment_name])
        resource.setrlimit(resource_kind, (value, value))


def _run(request_path: Path) -> dict[str, Any]:
    import hashlib
    import importlib.metadata

    from sklearn.base import clone

    from polygraphml.adapters.datasets import TabularDatasetAdapter
    from polygraphml.adapters.models import SkopsModelAdapter
    from polygraphml.engine.bounded_compute import ComputeRequest, ComputeResult
    from polygraphml.errors import PolygraphError

    request = ComputeRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    frame = TabularDatasetAdapter().load(Path(request.dataset_path))
    required = {request.target_column, request.split_column}
    if not required.issubset({str(column) for column in frame.columns}):
        raise PolygraphError("MAPPING_INCOMPLETE", "Mapped target or split column is absent.")
    model = SkopsModelAdapter().load(Path(request.model_path))
    feature_columns = _feature_columns(model, frame, request)
    train_mask = frame[request.split_column].astype(str) == "train"
    test_mask = frame[request.split_column].astype(str) == "test"
    if not train_mask.any() or not test_mask.any():
        raise PolygraphError(
            "MAPPING_INCOMPLETE", "Declared split must contain train and test rows."
        )
    reproduced = _score(
        model,
        frame.loc[test_mask, feature_columns],
        frame.loc[test_mask, request.target_column],
        request.metric,
    )
    corrected: float | None = None
    if request.operation == "correct":
        removed = set(request.removed_features)
        kept = [feature for feature in feature_columns if feature not in removed]
        if not kept or not removed.intersection(feature_columns):
            raise PolygraphError(
                "EXECUTION_UNSUPPORTED", "Correction must remove a mapped model feature."
            )
        challenger = clone(model)
        challenger.fit(frame.loc[train_mask, kept], frame.loc[train_mask, request.target_column])
        corrected = _score(
            challenger,
            frame.loc[test_mask, kept],
            frame.loc[test_mask, request.target_column],
            request.metric,
        )
    test_target = frame.loc[test_mask, request.target_column]
    test_positive = int((test_target.astype(str) == "1").sum())
    split_material = "|".join(str(index) for index in frame.index[test_mask])
    return ComputeResult(
        reproduced=reproduced,
        corrected=corrected,
        feature_columns=feature_columns,
        split_hash=hashlib.sha256(split_material.encode()).hexdigest(),
        package_versions={
            package: importlib.metadata.version(package)
            for package in ("pandas", "scikit-learn", "skops")
        },
        train_rows=int(train_mask.sum()),
        test_rows=int(test_mask.sum()),
        test_positive=test_positive,
        test_negative=int(test_mask.sum()) - test_positive,
    ).model_dump(mode="json")


def _feature_columns(model: Any, frame: Any, request: Any) -> list[str]:
    names = getattr(model, "feature_names_in_", None)
    if names is not None:
        return [str(name) for name in names]
    excluded = {
        request.target_column,
        request.split_column,
        request.entity_column,
        request.time_column,
    }
    return [str(column) for column in frame.columns if column not in excluded]


def _score(model: Any, features: Any, target: Any, metric: str) -> float:
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

    if metric == "roc_auc":
        if not hasattr(model, "predict_proba"):
            from polygraphml.errors import PolygraphError

            raise PolygraphError("EXECUTION_UNSUPPORTED", "Model has no probabilities.")
        return float(roc_auc_score(target, model.predict_proba(features)[:, 1]))
    predictions = model.predict(features)
    if metric == "accuracy":
        return float(accuracy_score(target, predictions))
    if metric == "f1":
        return float(f1_score(target, predictions))
    raise ValueError("Unsupported metric")


def main() -> int:
    result_path = Path(sys.argv[2])
    try:
        _apply_limits()
        payload = _run(Path(sys.argv[1]))
        return_code = 0
    except Exception as exc:
        from polygraphml.errors import PolygraphError

        payload = {
            "code": exc.code if isinstance(exc, PolygraphError) else "EXECUTION_FAILED",
            "message": (
                exc.message
                if isinstance(exc, PolygraphError)
                else "Bounded model evaluation failed."
            ),
        }
        return_code = 1
    result_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
