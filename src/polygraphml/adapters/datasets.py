from __future__ import annotations

from pathlib import Path

import pandas as pd

from polygraphml.domain.models import DatasetColumnProfile, DatasetProfile
from polygraphml.errors import PolygraphError


class TabularDatasetAdapter:
    def load(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        try:
            if suffix == ".csv":
                frame = pd.read_csv(path)
            elif suffix == ".parquet":
                frame = pd.read_parquet(path)
            else:
                raise PolygraphError("INVALID_ARTIFACT", "Unsupported dataset extension.")
        except PolygraphError:
            raise
        except Exception as exc:
            raise PolygraphError(
                "INVALID_ARTIFACT",
                "Dataset could not be parsed.",
                detail={"reason": type(exc).__name__},
            ) from exc
        if frame.empty or frame.shape[1] < 2:
            raise PolygraphError(
                "INVALID_ARTIFACT", "Dataset must contain rows and at least two columns."
            )
        if len(frame.columns) != len(set(str(column) for column in frame.columns)):
            raise PolygraphError("INVALID_ARTIFACT", "Dataset column names must be unique.")
        return frame

    def profile(
        self,
        path: Path,
        artifact_id: str,
        sha256: str,
        target_column: str | None = None,
    ) -> DatasetProfile:
        frame = self.load(path)
        columns: list[DatasetColumnProfile] = []
        for column_name in frame.columns:
            series = frame[column_name]
            samples = [str(value)[:80] for value in series.dropna().drop_duplicates().head(5)]
            columns.append(
                DatasetColumnProfile(
                    name=str(column_name),
                    dtype=str(series.dtype),
                    missing_fraction=float(series.isna().mean()),
                    cardinality=int(series.nunique(dropna=True)),
                    sample_values=samples,
                )
            )
        balance: dict[str, float] = {}
        if target_column and target_column in frame:
            balance = {
                str(key): float(value)
                for key, value in frame[target_column].value_counts(normalize=True).items()
            }
        return DatasetProfile(
            artifact_id=artifact_id,
            row_count=int(frame.shape[0]),
            column_count=int(frame.shape[1]),
            columns=columns,
            target_balance=balance,
            sha256=sha256,
        )
