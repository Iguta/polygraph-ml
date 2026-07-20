from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from polygraphml.api.container import AppContainer, build_container
from polygraphml.api.main import create_app
from polygraphml.config import Settings


@pytest.fixture
def app_stack(tmp_path: Path) -> Iterator[tuple[TestClient, AppContainer, Settings]]:
    settings = Settings(
        environment="test",
        agent_mode="fixture",
        database_path=tmp_path / "polygraphml.db",
        artifact_root=tmp_path / "artifacts",
        worker_poll_seconds=0.01,
        worker_lease_seconds=5,
    )
    container = build_container(settings)
    with TestClient(create_app(settings, container)) as client:
        yield client, container, settings


@pytest.fixture
def authorized_client(
    app_stack: tuple[TestClient, AppContainer, Settings],
) -> tuple[TestClient, AppContainer, Settings, dict[str, str]]:
    client, container, settings = app_stack
    response = client.post("/api/v1/sessions")
    assert response.status_code == 201
    token = response.json()["data"]["access_token"]
    return client, container, settings, {"Authorization": f"Bearer {token}"}
