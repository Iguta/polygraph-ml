from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

import boto3

from polygraphml.config import Settings
from polygraphml.domain.models import ArtifactKind
from polygraphml.errors import PolygraphError

REJECTED_SUFFIXES = {".pkl", ".pickle", ".joblib", ".cloudpickle", ".dill"}
ALLOWED_SUFFIXES: dict[ArtifactKind, set[str]] = {
    ArtifactKind.DATASET: {".csv", ".parquet"},
    ArtifactKind.MODEL: {".skops", ".json", ".ubj", ".onnx"},
    ArtifactKind.NOTEBOOK: {".ipynb"},
    ArtifactKind.SOURCE: {".py", ".txt", ".md"},
    ArtifactKind.MANIFEST: {".yaml", ".yml"},
}


@dataclass(frozen=True, slots=True)
class UploadDeclaration:
    client_id: str
    filename: str
    kind: ArtifactKind
    size_bytes: int
    sha256: str
    media_type: str


class ArtifactStore(Protocol):
    root: Path

    def key(self, project_id: str, client_id: str, filename: str) -> str: ...

    def path_for_key(self, storage_key: str) -> Path: ...

    def write(self, storage_key: str, content: bytes, max_bytes: int) -> tuple[int, str]: ...

    def verify(self, storage_key: str, size_bytes: int, sha256: str) -> Path: ...

    def presign_put(
        self, storage_key: str, media_type: str, sha256: str
    ) -> tuple[str, dict[str, str]] | None: ...

    def presign_get(self, storage_key: str) -> str | None: ...

    def delete_project(self, project_id: str) -> None: ...


def validate_filename(filename: str, kind: ArtifactKind) -> str:
    if not filename or "\x00" in filename:
        raise PolygraphError("INVALID_ARTIFACT", "Artifact filename is invalid.")
    pure = PurePosixPath(filename.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 1:
        raise PolygraphError("INVALID_ARTIFACT", "Artifact filename must be a plain filename.")
    suffix = pure.suffix.lower()
    if suffix in REJECTED_SUFFIXES:
        raise PolygraphError(
            "UNSAFE_ARTIFACT",
            "Pickle-family model artifacts are not accepted.",
            detail={"suffix": suffix},
        )
    if suffix not in ALLOWED_SUFFIXES[kind]:
        raise PolygraphError(
            "INVALID_ARTIFACT",
            f"{suffix or 'Extensionless files'} are not supported for {kind.value} artifacts.",
            detail={"allowed_suffixes": sorted(ALLOWED_SUFFIXES[kind])},
        )
    return pure.name


def validate_declaration(declaration: UploadDeclaration, settings: Settings) -> None:
    validate_filename(declaration.filename, declaration.kind)
    if declaration.size_bytes < 1 or declaration.size_bytes > settings.max_artifact_bytes:
        raise PolygraphError(
            "ARTIFACT_TOO_LARGE",
            "Artifact size is outside the accepted range.",
            detail={"max_bytes": settings.max_artifact_bytes},
        )
    if len(declaration.sha256) != 64 or any(
        character not in "0123456789abcdef" for character in declaration.sha256
    ):
        raise PolygraphError("INVALID_ARTIFACT", "sha256 must be lowercase hexadecimal.")


def validate_archive_member(
    path: str, *, is_symlink: bool = False, is_device: bool = False
) -> None:
    pure = PurePosixPath(path.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise PolygraphError("UNSAFE_ARTIFACT", "Archive contains an unsafe path.")
    if is_symlink or is_device:
        raise PolygraphError("UNSAFE_ARTIFACT", "Archive links and device files are rejected.")
    if len(pure.parts) > 20 or len(str(pure)) > 300:
        raise PolygraphError("UNSAFE_ARTIFACT", "Archive path exceeds safety limits.")


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def key(self, project_id: str, client_id: str, filename: str) -> str:
        safe_name = validate_filename(filename, self._kind_from_filename(filename))
        if not client_id.replace("-", "").replace("_", "").isalnum():
            raise PolygraphError("INVALID_ARTIFACT", "client_id contains invalid characters.")
        return f"{project_id}/{client_id}/{safe_name}"

    @staticmethod
    def _kind_from_filename(filename: str) -> ArtifactKind:
        suffix = Path(filename).suffix.lower()
        for kind, suffixes in ALLOWED_SUFFIXES.items():
            if suffix in suffixes:
                return kind
        if suffix in REJECTED_SUFFIXES:
            return ArtifactKind.MODEL
        raise PolygraphError("INVALID_ARTIFACT", "Unsupported artifact extension.")

    def path_for_key(self, storage_key: str) -> Path:
        pure = PurePosixPath(storage_key)
        if pure.is_absolute() or ".." in pure.parts:
            raise PolygraphError("UNSAFE_ARTIFACT", "Storage key is unsafe.")
        path = (self.root / Path(*pure.parts)).resolve()
        root = self.root.resolve()
        if path != root and root not in path.parents:
            raise PolygraphError("UNSAFE_ARTIFACT", "Storage key escapes the artifact root.")
        return path

    def write(self, storage_key: str, content: bytes, max_bytes: int) -> tuple[int, str]:
        if not content or len(content) > max_bytes:
            raise PolygraphError("ARTIFACT_TOO_LARGE", "Upload size is outside the accepted range.")
        path = self.path_for_key(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".part")
        temporary.write_bytes(content)
        os.replace(temporary, path)
        return len(content), hashlib.sha256(content).hexdigest()

    def verify(self, storage_key: str, size_bytes: int, sha256: str) -> Path:
        path = self.path_for_key(storage_key)
        if not path.is_file():
            raise PolygraphError("INVALID_ARTIFACT", "Uploaded artifact was not found.")
        actual_size = path.stat().st_size
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_size != size_bytes or actual_hash != sha256:
            raise PolygraphError(
                "INVALID_ARTIFACT",
                "Uploaded artifact does not match its declaration.",
                detail={
                    "size_matches": actual_size == size_bytes,
                    "hash_matches": actual_hash == sha256,
                },
            )
        return path

    def presign_put(
        self, storage_key: str, media_type: str, sha256: str
    ) -> tuple[str, dict[str, str]] | None:
        return None

    def presign_get(self, storage_key: str) -> str | None:
        return None

    def delete_project(self, project_id: str) -> None:
        project_root = self.path_for_key(project_id)
        if not project_root.exists():
            return
        for path in sorted(project_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        project_root.rmdir()


class S3ArtifactStore:
    """Encrypted S3 object store with a bounded worker-side read cache."""

    def __init__(
        self,
        bucket: str,
        region: str,
        cache_root: Path,
        *,
        client: Any | None = None,
    ) -> None:
        self.bucket = bucket
        self.root = cache_root
        self.root.mkdir(parents=True, exist_ok=True)
        self.client = client or boto3.client("s3", region_name=region)

    @staticmethod
    def _object_key(storage_key: str) -> str:
        pure = PurePosixPath(storage_key)
        if pure.is_absolute() or ".." in pure.parts or not pure.parts:
            raise PolygraphError("UNSAFE_ARTIFACT", "Storage key is unsafe.")
        return f"projects/{pure.as_posix()}"

    def key(self, project_id: str, client_id: str, filename: str) -> str:
        safe_name = validate_filename(filename, LocalArtifactStore._kind_from_filename(filename))
        if not client_id.replace("-", "").replace("_", "").isalnum():
            raise PolygraphError("INVALID_ARTIFACT", "client_id contains invalid characters.")
        return f"{project_id}/{client_id}/{safe_name}"

    def path_for_key(self, storage_key: str) -> Path:
        pure = PurePosixPath(storage_key)
        if pure.is_absolute() or ".." in pure.parts:
            raise PolygraphError("UNSAFE_ARTIFACT", "Storage key is unsafe.")
        path = (self.root / Path(*pure.parts)).resolve()
        root = self.root.resolve()
        if path != root and root not in path.parents:
            raise PolygraphError("UNSAFE_ARTIFACT", "Storage key escapes the artifact cache.")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".part")
            try:
                self.client.download_file(
                    self.bucket, self._object_key(storage_key), str(temporary)
                )
                os.replace(temporary, path)
            except Exception as exc:
                temporary.unlink(missing_ok=True)
                raise PolygraphError(
                    "INVALID_ARTIFACT", "Artifact could not be downloaded."
                ) from exc
        return path

    def write(self, storage_key: str, content: bytes, max_bytes: int) -> tuple[int, str]:
        if not content or len(content) > max_bytes:
            raise PolygraphError("ARTIFACT_TOO_LARGE", "Upload size is outside the accepted range.")
        sha256 = hashlib.sha256(content).hexdigest()
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._object_key(storage_key),
            Body=content,
            ServerSideEncryption="AES256",
            Metadata={"sha256": sha256},
        )
        cache_path = (self.root / storage_key).resolve()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(content)
        return len(content), sha256

    def verify(self, storage_key: str, size_bytes: int, sha256: str) -> Path:
        try:
            head = self.client.head_object(
                Bucket=self.bucket, Key=self._object_key(storage_key), ChecksumMode="ENABLED"
            )
        except Exception as exc:
            raise PolygraphError("INVALID_ARTIFACT", "Uploaded artifact was not found.") from exc
        actual_size = int(head.get("ContentLength", -1))
        actual_hash = str(head.get("Metadata", {}).get("sha256", ""))
        if actual_size != size_bytes or actual_hash != sha256:
            raise PolygraphError(
                "INVALID_ARTIFACT",
                "Uploaded artifact does not match its declaration.",
                detail={
                    "size_matches": actual_size == size_bytes,
                    "hash_matches": actual_hash == sha256,
                },
            )
        # Verification is intentionally metadata-only. The API can complete a
        # direct upload without downloading user bytes; workers fetch artifacts
        # later through path_for_key inside the execution boundary.
        return (self.root / storage_key).resolve()

    def presign_put(
        self, storage_key: str, media_type: str, sha256: str
    ) -> tuple[str, dict[str, str]]:
        headers = {"Content-Type": media_type, "x-amz-meta-sha256": sha256}
        url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": self._object_key(storage_key),
                "ContentType": media_type,
                "Metadata": {"sha256": sha256},
                "ServerSideEncryption": "AES256",
            },
            ExpiresIn=900,
        )
        headers["x-amz-server-side-encryption"] = "AES256"
        return str(url), headers

    def presign_get(self, storage_key: str) -> str:
        return str(
            self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": self._object_key(storage_key)},
                ExpiresIn=900,
            )
        )

    def delete_project(self, project_id: str) -> None:
        prefix = self._object_key(project_id).rstrip("/") + "/"
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if objects:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
        local = self.root / project_id
        if local.exists():
            for path in sorted(local.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            local.rmdir()
