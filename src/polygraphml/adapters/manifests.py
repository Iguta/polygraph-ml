from __future__ import annotations

from pathlib import PurePosixPath

import yaml
from pydantic import Field, HttpUrl, model_validator

from polygraphml.domain.models import (
    ArtifactKind,
    FeatureContext,
    Scenario,
    StrictModel,
)
from polygraphml.errors import PolygraphError

MAX_MANIFEST_BYTES = 256 * 1024
REQUIRED_ARTIFACT_KINDS = {
    ArtifactKind.DATASET,
    ArtifactKind.MODEL,
    ArtifactKind.NOTEBOOK,
}
KIND_SUFFIXES: dict[ArtifactKind, frozenset[str]] = {
    ArtifactKind.DATASET: frozenset({".csv", ".parquet"}),
    ArtifactKind.MODEL: frozenset({".skops", ".json", ".ubj", ".onnx"}),
    ArtifactKind.NOTEBOOK: frozenset({".ipynb"}),
    ArtifactKind.SOURCE: frozenset({".py", ".md", ".txt"}),
    ArtifactKind.MANIFEST: frozenset({".yaml", ".yml"}),
}


def validate_manifest_path(value: str) -> str:
    if not value or "\\" in value:
        raise ValueError("Manifest paths must use non-empty POSIX-relative paths.")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("Manifest paths must be normalized and repository-relative.")
    return path.as_posix()


class ManifestMapping(StrictModel):
    target_column: str = Field(min_length=1, max_length=200)
    split_column: str = Field(min_length=1, max_length=200)
    entity_column: str | None = Field(default=None, max_length=200)
    time_column: str | None = Field(default=None, max_length=200)
    reported_metric_location: str | None = Field(default=None, max_length=500)


class ManifestProvenance(StrictModel):
    dataset_source_url: HttpUrl
    license_name: str = Field(min_length=2, max_length=100)
    license_url: HttpUrl | None = None
    artifact_hashes: dict[str, str] = Field(min_length=3, max_length=20)


class PolygraphManifest(StrictModel):
    schema_version: str = Field(pattern=r"^1$")
    artifacts: dict[ArtifactKind, str] = Field(min_length=3, max_length=20)
    mapping: ManifestMapping
    scenario: Scenario
    features: dict[str, FeatureContext] = Field(default_factory=dict, max_length=200)
    provenance: ManifestProvenance

    @model_validator(mode="after")
    def validate_artifacts(self) -> PolygraphManifest:
        missing = REQUIRED_ARTIFACT_KINDS - set(self.artifacts)
        if missing:
            kinds = ", ".join(sorted(kind.value for kind in missing))
            raise ValueError(f"Manifest is missing required artifacts: {kinds}.")
        normalized: dict[ArtifactKind, str] = {}
        seen_paths: set[str] = set()
        for kind, raw_path in self.artifacts.items():
            path = validate_manifest_path(raw_path)
            if path in seen_paths:
                raise ValueError("Manifest artifact paths must be unique.")
            if PurePosixPath(path).suffix.lower() not in KIND_SUFFIXES[kind]:
                raise ValueError(f"Artifact path {path} has an invalid suffix for {kind.value}.")
            seen_paths.add(path)
            normalized[kind] = path
        normalized_hashes = {
            validate_manifest_path(path): digest
            for path, digest in self.provenance.artifact_hashes.items()
        }
        extra_hashes = set(normalized_hashes) - set(normalized.values())
        if extra_hashes:
            raise ValueError("Manifest hashes may reference declared artifacts only.")
        for path in normalized.values():
            digest = normalized_hashes.get(path)
            if (
                digest is None
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise ValueError(f"Manifest requires a lowercase SHA-256 for {path}.")
        self.artifacts = normalized
        self.provenance.artifact_hashes = normalized_hashes
        return self


def load_manifest_bytes(content: bytes) -> PolygraphManifest:
    if not content or len(content) > MAX_MANIFEST_BYTES:
        raise PolygraphError(
            "INVALID_REPOSITORY",
            "The PolygraphML manifest is empty or exceeds 256 KiB.",
        )
    try:
        payload = yaml.safe_load(content.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Manifest root must be an object.")
        return PolygraphManifest.model_validate(payload)
    except (UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
        raise PolygraphError(
            "INVALID_REPOSITORY",
            "The PolygraphML manifest is invalid.",
            detail={"reason": type(exc).__name__},
        ) from exc
