from __future__ import annotations

import ast
import re
from pathlib import Path

import nbformat
from pydantic import BaseModel, ConfigDict, Field

from polygraphml.errors import PolygraphError


class NotebookClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    value: float
    source_ref: str


class NotebookInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_cells: int
    split_cells: list[str] = Field(default_factory=list)
    preprocessing_cells: list[str] = Field(default_factory=list)
    training_cells: list[str] = Field(default_factory=list)
    metric_cells: list[str] = Field(default_factory=list)
    data_read_cells: list[str] = Field(default_factory=list)
    claims: list[NotebookClaim] = Field(default_factory=list)
    preprocessing_before_split: bool = False


METRIC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:roc[_ ]?auc|auc)\s*[:=]\s*([01](?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"accuracy\s*[:=]\s*([01](?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"f1\s*[:=]\s*([01](?:\.\d+)?)", re.IGNORECASE),
)


class NotebookInspector:
    def inspect(self, path: Path) -> NotebookInspection:
        try:
            notebook = nbformat.read(path, as_version=4)
        except Exception as exc:
            raise PolygraphError("INVALID_ARTIFACT", "Notebook could not be parsed.") from exc

        inspection = NotebookInspection(code_cells=0)
        fit_position: int | None = None
        split_position: int | None = None

        for index, cell in enumerate(notebook.cells):
            source_ref = f"{path.name}#cell={index}"
            if cell.cell_type != "code":
                continue
            inspection.code_cells += 1
            source = str(cell.source)
            try:
                ast.parse(source)
            except SyntaxError:
                pass
            lowered = source.lower()
            if any(token in lowered for token in ("read_csv", "read_parquet")):
                inspection.data_read_cells.append(source_ref)
            if any(
                token in lowered for token in ("train_test_split", "groupkfold", "timeseriessplit")
            ):
                inspection.split_cells.append(source_ref)
                split_position = index if split_position is None else min(split_position, index)
            if any(
                token in lowered for token in ("fit_transform", "standardscaler", "onehotencoder")
            ):
                inspection.preprocessing_cells.append(source_ref)
                fit_position = index if fit_position is None else min(fit_position, index)
            if re.search(r"\.(fit|fit_transform)\s*\(", source):
                inspection.training_cells.append(source_ref)
            if any(token in lowered for token in ("roc_auc_score", "accuracy_score", "f1_score")):
                inspection.metric_cells.append(source_ref)

            output_text = "\n".join(self._output_text(output) for output in cell.get("outputs", []))
            for pattern in METRIC_PATTERNS:
                match = pattern.search(output_text)
                if match:
                    metric = (
                        "roc_auc"
                        if "auc" in pattern.pattern.lower()
                        else pattern.pattern.split("\\")[0]
                    )
                    inspection.claims.append(
                        NotebookClaim(
                            metric=metric,
                            value=float(match.group(1)),
                            source_ref=source_ref,
                        )
                    )
                    break

        inspection.preprocessing_before_split = (
            fit_position is not None
            and split_position is not None
            and fit_position < split_position
        )
        return inspection

    @staticmethod
    def _output_text(output: object) -> str:
        if not isinstance(output, dict):
            return ""
        if output.get("output_type") == "stream":
            text = output.get("text", "")
            return "".join(text) if isinstance(text, list) else str(text)
        data = output.get("data", {})
        if isinstance(data, dict):
            value = data.get("text/plain", "")
            return "".join(value) if isinstance(value, list) else str(value)
        return ""
