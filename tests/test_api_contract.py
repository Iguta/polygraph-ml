from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from polygraphml.api.container import AppContainer
from polygraphml.config import Settings
from polygraphml.domain.models import ArtifactKind
from polygraphml.errors import PolygraphError
from polygraphml.services.projects import ProjectService, adapter_for


def test_auth_scope_and_strict_request_contract(
    authorized_client: tuple[TestClient, AppContainer, Settings, dict[str, str]],
) -> None:
    client, _, _, headers = authorized_client
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {
        "status": "ready",
        "agent_mode": "fixture",
        "live_agent_ready": False,
    }
    assert client.get("/version").json() == {
        "api_version": "1.2",
        "release_version": "0.2.0",
        "build_sha": "unknown",
        "evaluator_version": "0.2.0",
    }
    assert client.get("/api/v1/benchmarks").status_code == 401
    benchmarks = client.get("/api/v1/benchmarks", headers=headers).json()["data"]
    assert benchmarks[0]["benchmark_id"] == "uci_bank_marketing_duration_v1"
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "strict",
            "source": {"type": "upload"},
            "unknown": "rejected",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert response.json()["error"]["detail"]["fields"][0]["location"].startswith("body")


def test_project_helper_rejects_non_github_and_classifies_adapters() -> None:
    assert adapter_for(ArtifactKind.MODEL, "model.skops") == ("skops", "supported")
    assert adapter_for(ArtifactKind.MODEL, "model.json") == ("xgboost", "limited")
    assert adapter_for(ArtifactKind.MODEL, "model.onnx") == ("onnx", "limited")
    assert adapter_for(ArtifactKind.NOTEBOOK, "analysis.ipynb") == (
        "ipynb-static",
        "supported",
    )
    assert ProjectService._parse_github_url("https://github.com/openai/openai-python.git") == (
        "openai",
        "openai-python",
    )
    assert ProjectService._kind_for_path("models/model.pkl") is None
    with pytest.raises(PolygraphError, match=r"Only public github\.com"):
        ProjectService._parse_github_url("https://example.com/owner/repo")
    with pytest.raises(PolygraphError, match="owner and name"):
        ProjectService._parse_github_url("https://github.com/owner")


def test_upload_checksum_scope_and_complete_mapping_gate(
    authorized_client: tuple[TestClient, AppContainer, Settings, dict[str, str]],
) -> None:
    client, _, _, headers = authorized_client
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Upload", "source": {"type": "upload"}},
    ).json()["data"]
    content = b"feature,target,split\n1,0,train\n2,1,test\n"
    digest = hashlib.sha256(content).hexdigest()
    declared = client.post(
        f"/api/v1/projects/{project['project_id']}/artifacts/presign",
        headers=headers,
        json={
            "artifacts": [
                {
                    "client_id": "dataset",
                    "filename": "dataset.csv",
                    "kind": "dataset",
                    "size_bytes": len(content),
                    "sha256": digest,
                    "media_type": "text/csv",
                }
            ]
        },
    )
    assert declared.status_code == 200
    upload = declared.json()["data"]["uploads"][0]
    assert client.put(upload["url"], headers=headers, content=content).status_code == 204
    completed = client.post(
        f"/api/v1/projects/{project['project_id']}/artifacts/complete",
        headers=headers,
        json={"artifact_ids": [upload["artifact_id"]]},
    )
    assert completed.status_code == 200
    assert completed.json()["data"]["status"] == "ready_for_mapping"

    audit = client.post(
        "/api/v1/audits",
        headers={**headers, "Idempotency-Key": "incomplete-map-1"},
        json={
            "project_id": project["project_id"],
            "scenario_revision": 1,
            "mode": "complete_audit",
        },
    )
    assert audit.status_code == 400
    assert audit.json()["error"]["code"] == "MAPPING_INCOMPLETE"


def test_local_upload_stream_rejects_more_than_declared_size(
    authorized_client: tuple[TestClient, AppContainer, Settings, dict[str, str]],
) -> None:
    client, _, _, headers = authorized_client
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Bounded upload", "source": {"type": "upload"}},
    ).json()["data"]
    declared_content = b"1234567890"
    declaration = client.post(
        f"/api/v1/projects/{project['project_id']}/artifacts/presign",
        headers=headers,
        json={
            "artifacts": [
                {
                    "client_id": "dataset",
                    "filename": "dataset.csv",
                    "kind": "dataset",
                    "size_bytes": len(declared_content),
                    "sha256": hashlib.sha256(declared_content).hexdigest(),
                    "media_type": "text/csv",
                }
            ]
        },
    ).json()["data"]["uploads"][0]
    response = client.put(
        declaration["url"],
        headers=headers,
        content=declared_content + b"overflow",
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "ARTIFACT_TOO_LARGE"


def test_project_ownership_and_disposable_deletion(
    authorized_client: tuple[TestClient, AppContainer, Settings, dict[str, str]],
) -> None:
    client, container, _, headers = authorized_client
    project = client.post(
        "/api/v1/projects/from-benchmark",
        headers=headers,
        json={"benchmark_id": "synthetic_campaign_leak_v1"},
    ).json()["data"]
    project_id = project["project_id"]
    assert client.get(f"/api/v1/projects/{project_id}", headers=headers).status_code == 200
    project_root = container.artifacts.root / project_id
    assert project_root.exists()

    second_token = client.post("/api/v1/sessions").json()["data"]["access_token"]
    second_headers = {"Authorization": f"Bearer {second_token}"}
    assert client.get(f"/api/v1/projects/{project_id}", headers=second_headers).status_code == 404

    deleted = client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert deleted.status_code == 204
    assert not project_root.exists()
    assert client.get(f"/api/v1/projects/{project_id}", headers=headers).status_code == 404
