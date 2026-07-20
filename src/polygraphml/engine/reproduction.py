from __future__ import annotations

import hashlib
import importlib.metadata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

from polygraphml.adapters.datasets import TabularDatasetAdapter
from polygraphml.adapters.models import SkopsModelAdapter
from polygraphml.adapters.notebooks import NotebookInspection, NotebookInspector
from polygraphml.domain.models import (
    Artifact,
    ArtifactMapping,
    MetricComparison,
    MetricValue,
    Provenance,
    ReproductionTier,
)
from polygraphml.engine.probes import ablation_scores
from polygraphml.errors import PolygraphError


@dataclass(slots=True)
class ReproductionResult:
    tier: ReproductionTier
    metric_comparison: MetricComparison
    provenance: Provenance
    frame: pd.DataFrame
    model: Any
    notebook: NotebookInspection
    feature_columns: list[str]


class ReproductionEngine:
    def __init__(self) -> None:
        self.dataset_adapter = TabularDatasetAdapter()
        self.model_adapter = SkopsModelAdapter()
        self.notebook_inspector = NotebookInspector()

    def reproduce(
        self,
        mapping: ArtifactMapping,
        artifacts: dict[str, Artifact],
        paths: dict[str, Path],
        metric: Literal["roc_auc", "accuracy", "f1"],
        tolerance: float = 0.005,
    ) -> ReproductionResult:
        required = (
            mapping.dataset_artifact_id,
            mapping.model_artifact_id,
            mapping.notebook_artifact_id,
            mapping.target_column,
            mapping.split_column,
        )
        if any(value is None for value in required):
            raise PolygraphError(
                "MAPPING_INCOMPLETE", "Dataset, model, notebook, target, and split are required."
            )
        dataset_id = str(mapping.dataset_artifact_id)
        model_id = str(mapping.model_artifact_id)
        notebook_id = str(mapping.notebook_artifact_id)
        target_column = str(mapping.target_column)
        split_column = str(mapping.split_column)
        frame = self.dataset_adapter.load(paths[dataset_id])
        if target_column not in frame or split_column not in frame:
            raise PolygraphError("MAPPING_INCOMPLETE", "Mapped target or split column is absent.")
        model = self.model_adapter.load(paths[model_id])
        notebook = self.notebook_inspector.inspect(paths[notebook_id])
        feature_columns = self._feature_columns(model, frame, mapping)
        test_mask = frame[split_column].astype(str) == "test"
        if not test_mask.any():
            raise PolygraphError("MAPPING_INCOMPLETE", "Declared split has no test rows.")
        reproduced = self._score(
            model,
            frame.loc[test_mask, feature_columns],
            frame.loc[test_mask, target_column],
            metric,
        )
        claim = next((claim for claim in notebook.claims if claim.metric == metric), None)
        reported = (
            MetricValue(
                value=claim.value,
                protocol_id="reported_claim_unverified",
                reproduction_tier="reported_claim",
                provenance=claim.source_ref,
            )
            if claim is not None
            else None
        )
        status: Literal["within_tolerance", "outside_tolerance", "unavailable", "not_claimed"] = (
            "not_claimed"
        )
        if reported is not None:
            status = (
                "within_tolerance"
                if abs(reported.value - reproduced) <= tolerance
                else "outside_tolerance"
            )
        split_material = "|".join(str(index) for index in frame.index[test_mask])
        provenance = Provenance(
            artifact_hashes=[
                f"sha256:{artifacts[item].sha256}" for item in (dataset_id, model_id, notebook_id)
            ],
            package_versions={
                package: importlib.metadata.version(package)
                for package in ("pandas", "scikit-learn", "skops")
            },
            split_hash=hashlib.sha256(split_material.encode()).hexdigest(),
            feature_order=feature_columns,
        )
        comparison = MetricComparison(
            metric=metric,
            reported=reported,
            reproduced=MetricValue(
                value=reproduced,
                tolerance=tolerance,
                protocol_id="proto_original_v1",
                reproduction_tier=ReproductionTier.EXACT_SUPPORTED,
                provenance="compute:reproduction@1",
            ),
            corrected=None,
            reproduction_status=status,
        )
        return ReproductionResult(
            tier=ReproductionTier.EXACT_SUPPORTED,
            metric_comparison=comparison,
            provenance=provenance,
            frame=frame,
            model=model,
            notebook=notebook,
            feature_columns=feature_columns,
        )

    def correct(
        self,
        result: ReproductionResult,
        mapping: ArtifactMapping,
        removed_features: list[str],
    ) -> MetricComparison:
        target = str(mapping.target_column)
        split = str(mapping.split_column)
        baseline, corrected, _ = ablation_scores(
            result.model,
            result.frame,
            target,
            split,
            result.feature_columns,
            removed_features,
        )
        comparison = result.metric_comparison.model_copy(deep=True)
        comparison.reproduced = MetricValue(
            value=baseline,
            tolerance=comparison.reproduced.tolerance if comparison.reproduced else 0.005,
            protocol_id="proto_original_v1",
            reproduction_tier=result.tier,
            provenance="compute:reproduction@1",
        )
        comparison.corrected = MetricValue(
            value=corrected,
            tolerance=0.005,
            protocol_id="proto_corrected_v1",
            reproduction_tier=result.tier,
            provenance="compute:correction@1",
        )
        return comparison

    @staticmethod
    def _feature_columns(model: Any, frame: pd.DataFrame, mapping: ArtifactMapping) -> list[str]:
        names = getattr(model, "feature_names_in_", None)
        if names is not None:
            return [str(name) for name in names]
        excluded = {
            mapping.target_column,
            mapping.split_column,
            mapping.entity_column,
            mapping.time_column,
        }
        return [str(column) for column in frame.columns if column not in excluded]

    @staticmethod
    def _score(model: Any, features: pd.DataFrame, target: pd.Series, metric: str) -> float:
        if metric == "roc_auc":
            if not hasattr(model, "predict_proba"):
                raise PolygraphError(
                    "EXECUTION_UNSUPPORTED", "Model does not expose probabilities."
                )
            return float(roc_auc_score(target, model.predict_proba(features)[:, 1]))
        predictions = model.predict(features)
        if metric == "accuracy":
            return float(accuracy_score(target, predictions))
        if metric == "f1":
            return float(f1_score(target, predictions))
        raise PolygraphError("INVALID_REQUEST", "Unsupported metric.")
