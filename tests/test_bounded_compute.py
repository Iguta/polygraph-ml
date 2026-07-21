from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import ClassVar

import pytest

from polygraphml.engine.bounded_compute import BoundedComputeRunner, ComputeRequest
from polygraphml.errors import PolygraphError


def _request() -> ComputeRequest:
    return ComputeRequest(
        operation="reproduce",
        dataset_path="/does/not/exist.csv",
        model_path="/does/not/exist.skops",
        target_column="target",
        split_column="split",
        metric="roc_auc",
    )


def test_bounded_runner_uses_sanitized_environment_and_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 12345
        result: ClassVar[dict[str, object]] = {
            "reproduced": 0.75,
            "corrected": None,
            "feature_columns": ["signal"],
            "split_hash": "a" * 64,
            "package_versions": {},
            "train_rows": 10,
            "test_rows": 4,
            "test_positive": 2,
            "test_negative": 2,
        }

        def __init__(self, command: list[str], **kwargs: object) -> None:
            captured.update(kwargs)
            captured["command"] = command
            Path(command[-1]).write_text(json.dumps(self.result), encoding="utf-8")

        def wait(self, timeout: float | None = None) -> int:
            captured["timeout"] = timeout
            return 0

    monkeypatch.setattr(subprocess, "Popen", FakeProcess)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-propagate")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-propagate")

    result = BoundedComputeRunner().run(_request())

    environment = captured["env"]
    assert isinstance(environment, dict)
    assert "OPENAI_API_KEY" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert environment["OMP_NUM_THREADS"] == "1"
    assert captured["start_new_session"] is True
    assert result.test_rows == 4


def test_bounded_runner_terminates_process_group_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    killed: list[tuple[int, int]] = []

    class TimeoutProcess:
        pid = 24680

        def __init__(self, *_: object, **__: object) -> None:
            self.waits = 0

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired("compute", 0.01)
            return -9

    monkeypatch.setattr(subprocess, "Popen", TimeoutProcess)
    monkeypatch.setattr(os, "killpg", lambda pid, sig: killed.append((pid, sig)))

    with pytest.raises(PolygraphError) as captured:
        BoundedComputeRunner(wall_timeout_seconds=0.01).run(_request())

    assert captured.value.code == "EXECUTION_TIMEOUT"
    assert killed == [(24680, 9)]
