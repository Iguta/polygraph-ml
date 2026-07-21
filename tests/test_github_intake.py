from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any, ClassVar

import httpx
import pytest
import yaml

from polygraphml.domain.models import Artifact, ProjectStatus, Session, utc_now
from polygraphml.errors import PolygraphError

COMMIT = "a" * 40


def _repository_fixture() -> tuple[dict[str, bytes], bytes]:
    artifacts = {
        "artifacts/evaluation.csv": b"signal,target,split\n0,0,train\n1,1,test\n",
        "artifacts/model.ubj": b"safe-opaque-model",
        "analysis/evaluation.ipynb": json.dumps(
            {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {},
                "cells": [],
            }
        ).encode(),
    }
    manifest = {
        "schema_version": "1",
        "artifacts": {
            "dataset": "artifacts/evaluation.csv",
            "model": "artifacts/model.ubj",
            "notebook": "analysis/evaluation.ipynb",
        },
        "mapping": {
            "target_column": "target",
            "split_column": "split",
            "reported_metric_location": "cell:4",
        },
        "scenario": {
            "revision": 1,
            "target_definition": "Whether the customer accepts the offer",
            "row_entity": "One customer contact",
            "decision_time": "Before the current contact begins",
            "prediction_horizon": "Current contact response",
            "split_unit": "Customer",
            "intended_metric": "roc_auc",
        },
        "features": {
            "signal": {
                "description": "A signal documented before the current contact",
                "source_refs": ["https://example.test/dictionary#signal"],
            }
        },
        "provenance": {
            "dataset_source_url": "https://example.test/dataset",
            "license_name": "CC BY 4.0",
            "artifact_hashes": {
                path: hashlib.sha256(content).hexdigest() for path, content in artifacts.items()
            },
        },
    }
    return artifacts, yaml.safe_dump(manifest, sort_keys=False).encode()


class FakeGitHubClient:
    artifacts: ClassVar[dict[str, bytes]]
    manifest: ClassVar[bytes]
    artifacts, manifest = _repository_fixture()
    truncated: ClassVar[bool] = False
    fail_path: ClassVar[str | None] = None

    def __init__(self, *_: object, **__: object) -> None:
        pass

    async def __aenter__(self) -> FakeGitHubClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str, *, params: dict[str, str] | None = None) -> httpx.Response:
        del params
        if "/commits/" in url:
            return httpx.Response(200, json={"sha": COMMIT})
        if "/git/trees/" in url:
            all_artifacts = {".polygraphml.yml": self.manifest, **self.artifacts}
            return httpx.Response(
                200,
                json={
                    "truncated": self.truncated,
                    "tree": [
                        {"path": path, "type": "blob", "size": len(content)}
                        for path, content in all_artifacts.items()
                    ],
                },
            )
        path = url.split(f"/{COMMIT}/", maxsplit=1)[1]
        if path == self.fail_path:
            return httpx.Response(404, content=b"not found")
        content = self.manifest if path == ".polygraphml.yml" else self.artifacts[path]
        return httpx.Response(
            200,
            content=content,
            headers={"content-length": str(len(content))},
        )


def _session() -> Session:
    return Session(
        session_id="ses_github_test",
        token_hash=hashlib.sha256(b"github-test-token").hexdigest(),
        expires_at=utc_now() + timedelta(hours=1),
    )


async def test_manifest_github_import_is_pinned_hashed_and_ready(
    app_stack: tuple[Any, Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, container, _ = app_stack
    monkeypatch.setattr("polygraphml.services.projects.httpx.AsyncClient", FakeGitHubClient)
    session = _session()

    project = await container.projects.create_github_project(
        session, "Manifest project", "https://github.com/example/audit", "dev"
    )

    assert project.status == ProjectStatus.READY
    assert project.source.requested_ref == "dev"
    assert project.source.resolved_commit == COMMIT
    assert project.mapping.target_column == "target"
    assert project.mapping.reported_metric_source is not None
    assert project.current_scenario is not None
    assert project.current_scenario.decision_time == "Before the current contact begins"
    assert project.feature_context["signal"].source_refs
    imported = [container.repository.get(Artifact, item) for item in project.artifact_ids]
    assert len(imported) == 4
    assert all(
        artifact is not None and artifact.source_ref.endswith(f"@{COMMIT}") for artifact in imported
    )


@pytest.mark.parametrize("failure", ["truncated", "download"])
async def test_manifest_github_import_rejects_incomplete_repository_reads(
    app_stack: tuple[Any, Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    _, container, _ = app_stack

    class FailingClient(FakeGitHubClient):
        truncated = failure == "truncated"
        fail_path = "artifacts/model.ubj" if failure == "download" else None

    monkeypatch.setattr("polygraphml.services.projects.httpx.AsyncClient", FailingClient)
    session = _session()

    with pytest.raises(PolygraphError):
        await container.projects.create_github_project(
            session, "Rejected project", "https://github.com/example/audit", "main"
        )


async def test_manifest_github_import_rejects_hash_mismatch(
    app_stack: tuple[Any, Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, container, _ = app_stack

    class ChangedArtifactClient(FakeGitHubClient):
        artifacts: ClassVar[dict[str, bytes]] = {
            **FakeGitHubClient.artifacts,
            "artifacts/model.ubj": b"changed",
        }

    monkeypatch.setattr("polygraphml.services.projects.httpx.AsyncClient", ChangedArtifactClient)
    session = _session()

    with pytest.raises(PolygraphError, match="does not match"):
        await container.projects.create_github_project(
            session, "Hash mismatch", "https://github.com/example/audit", "main"
        )
