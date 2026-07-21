from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from polygraphml.adapters.datasets import TabularDatasetAdapter
from polygraphml.adapters.notebooks import NotebookInspection, NotebookInspector
from polygraphml.config import Settings
from polygraphml.domain.models import (
    Artifact,
    ArtifactMapping,
    ComputeExecutionProvenance,
    MetricComparison,
    MetricValue,
    Provenance,
    ReproductionTier,
)
from polygraphml.engine.bounded_compute import (
    BoundedComputeRunner,
    ComputeRequest,
)
from polygraphml.errors import PolygraphError


@dataclass(slots=True)
class ReproductionResult:
    tier: ReproductionTier
    metric_comparison: MetricComparison
    provenance: Provenance
    frame: pd.DataFrame
    notebook: NotebookInspection
    feature_columns: list[str]
    dataset_path: Path
    model_path: Path
    metric: Literal["roc_auc", "accuracy", "f1"]


class ReproductionEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        configured = settings or Settings()
        self.dataset_adapter = TabularDatasetAdapter()
        self.notebook_inspector = NotebookInspector()
        self.compute = BoundedComputeRunner(
            wall_timeout_seconds=configured.compute_wall_timeout_seconds,
            cpu_limit_seconds=configured.compute_cpu_limit_seconds,
            memory_limit_bytes=configured.compute_memory_limit_bytes,
            file_descriptor_limit=configured.compute_file_descriptor_limit,
        )

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
        notebook = self.notebook_inspector.inspect(paths[notebook_id])
        compute = self.compute.run(
            ComputeRequest(
                operation="reproduce",
                dataset_path=str(paths[dataset_id].resolve()),
                model_path=str(paths[model_id].resolve()),
                target_column=target_column,
                split_column=split_column,
                entity_column=mapping.entity_column,
                time_column=mapping.time_column,
                metric=metric,
            )
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
                if abs(reported.value - compute.reproduced) <= tolerance
                else "outside_tolerance"
            )
        provenance = Provenance(
            artifact_hashes=[
                f"sha256:{artifacts[item].sha256}" for item in (dataset_id, model_id, notebook_id)
            ],
            package_versions=compute.package_versions,
            split_hash=compute.split_hash,
            feature_order=compute.feature_columns,
            compute_execution=ComputeExecutionProvenance(
                wall_timeout_seconds=self.compute.wall_timeout_seconds,
                cpu_limit_seconds=self.compute.cpu_limit_seconds,
                memory_limit_bytes=self.compute.memory_limit_bytes,
                file_descriptor_limit=self.compute.file_descriptor_limit,
                train_rows=compute.train_rows,
                test_rows=compute.test_rows,
                test_positive=compute.test_positive,
                test_negative=compute.test_negative,
            ),
        )
        comparison = MetricComparison(
            metric=metric,
            reported=reported,
            reproduced=MetricValue(
                value=compute.reproduced,
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
            notebook=notebook,
            feature_columns=compute.feature_columns,
            dataset_path=paths[dataset_id].resolve(),
            model_path=paths[model_id].resolve(),
            metric=metric,
        )

    def correct(
        self,
        result: ReproductionResult,
        mapping: ArtifactMapping,
        removed_features: list[str],
    ) -> MetricComparison:
        compute = self.compute.run(
            ComputeRequest(
                operation="correct",
                dataset_path=str(result.dataset_path),
                model_path=str(result.model_path),
                target_column=str(mapping.target_column),
                split_column=str(mapping.split_column),
                entity_column=mapping.entity_column,
                time_column=mapping.time_column,
                metric=result.metric,
                removed_features=removed_features,
            )
        )
        if compute.corrected is None:
            raise PolygraphError("EXECUTION_FAILED", "Correction returned no corrected metric.")
        comparison = result.metric_comparison.model_copy(deep=True)
        comparison.reproduced = MetricValue(
            value=compute.reproduced,
            tolerance=comparison.reproduced.tolerance if comparison.reproduced else 0.005,
            protocol_id="proto_original_v1",
            reproduction_tier=result.tier,
            provenance="compute:reproduction@1",
        )
        comparison.corrected = MetricValue(
            value=compute.corrected,
            tolerance=0.005,
            protocol_id="proto_corrected_v1",
            reproduction_tier=result.tier,
            provenance="compute:correction@1",
        )
        return comparison
