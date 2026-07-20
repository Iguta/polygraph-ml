from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, cast

import skops.io as skops_io

from polygraphml.errors import PolygraphError


class SkopsModelAdapter:
    """Load standard sklearn objects only after the skops trust inspection succeeds."""

    allowed_untrusted_prefixes: tuple[str, ...] = (
        "sklearn.",
        "numpy.",
        "pandas.",
    )

    def inspect(self, path: Path) -> list[str]:
        try:
            untrusted = skops_io.get_untrusted_types(file=path)
        except Exception as exc:
            raise PolygraphError(
                "INVALID_ARTIFACT", "The skops model could not be inspected."
            ) from exc
        rejected = [
            type_name
            for type_name in untrusted
            if not type_name.startswith(self.allowed_untrusted_prefixes)
        ]
        if rejected:
            raise PolygraphError(
                "UNSAFE_ARTIFACT",
                "The skops model contains types outside the allowlist.",
                detail={"rejected_types": rejected},
            )
        return cast(list[str], untrusted)

    def load(self, path: Path) -> Any:
        trusted = self.inspect(path)
        try:
            model = skops_io.load(path, trusted=trusted)
        except Exception as exc:
            raise PolygraphError(
                "INVALID_ARTIFACT", "The skops model could not be loaded."
            ) from exc
        if not hasattr(model, "predict"):
            raise PolygraphError("INVALID_ARTIFACT", "The artifact is not a supported estimator.")
        module_name = type(model).__module__
        if not module_name.startswith("sklearn."):
            raise PolygraphError(
                "UNSAFE_ARTIFACT", "Only scikit-learn estimators are supported in skops MVP."
            )
        return model


class XGBoostModelInspector:
    required_keys: ClassVar[set[str]] = {"learner", "version"}

    def inspect_json(self, path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PolygraphError("INVALID_ARTIFACT", "XGBoost JSON is malformed.") from exc
        if not isinstance(payload, dict) or not self.required_keys.issubset(payload):
            raise PolygraphError(
                "INVALID_ARTIFACT", "Arbitrary JSON is not accepted as an XGBoost model."
            )
        return payload
