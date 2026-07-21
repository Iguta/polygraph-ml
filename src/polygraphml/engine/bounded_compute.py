from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field

from polygraphml.domain.models import StrictModel
from polygraphml.errors import PolygraphError

MAX_RESULT_BYTES = 1024 * 1024


class ComputeRequest(StrictModel):
    operation: Literal["reproduce", "correct"]
    dataset_path: str = Field(min_length=1)
    model_path: str = Field(min_length=1)
    target_column: str = Field(min_length=1)
    split_column: str = Field(min_length=1)
    entity_column: str | None = None
    time_column: str | None = None
    metric: Literal["roc_auc", "accuracy", "f1"]
    removed_features: list[str] = Field(default_factory=list, max_length=20)


class ComputeResult(StrictModel):
    reproduced: float
    corrected: float | None = None
    feature_columns: list[str]
    split_hash: str
    package_versions: dict[str, str]
    train_rows: int = Field(ge=0)
    test_rows: int = Field(ge=0)
    test_positive: int = Field(ge=0)
    test_negative: int = Field(ge=0)


class BoundedComputeRunner:
    """Run approved model evaluation in a resource-bounded child process.

    This reduces accidental resource exhaustion. It is deliberately not described as
    a security sandbox: the child retains the host network and kernel trust boundary.
    """

    def __init__(
        self,
        *,
        wall_timeout_seconds: float = 120,
        cpu_limit_seconds: int = 90,
        memory_limit_bytes: int = 2 * 1024 * 1024 * 1024,
        file_descriptor_limit: int = 64,
    ) -> None:
        self.wall_timeout_seconds = wall_timeout_seconds
        self.cpu_limit_seconds = cpu_limit_seconds
        self.memory_limit_bytes = memory_limit_bytes
        self.file_descriptor_limit = file_descriptor_limit

    def run(self, request: ComputeRequest) -> ComputeResult:
        with tempfile.TemporaryDirectory(prefix="polygraphml-compute-") as temporary:
            root = Path(temporary)
            request_path = root / "request.json"
            result_path = root / "result.json"
            request_path.write_text(request.model_dump_json(), encoding="utf-8")
            environment = {
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PYTHONHASHSEED": "0",
                "PYTHONNOUSERSITE": "1",
                "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "NUMEXPR_NUM_THREADS": "1",
                "VECLIB_MAXIMUM_THREADS": "1",
                "POLYGRAPHML_COMPUTE_CPU_SECONDS": str(self.cpu_limit_seconds),
                "POLYGRAPHML_COMPUTE_MEMORY_BYTES": str(self.memory_limit_bytes),
                "POLYGRAPHML_COMPUTE_NOFILE": str(self.file_descriptor_limit),
                "POLYGRAPHML_COMPUTE_FILE_BYTES": str(MAX_RESULT_BYTES),
                "TMPDIR": str(root),
            }
            process = subprocess.Popen(  # noqa: S603 - fixed interpreter and module
                [
                    sys.executable,
                    "-m",
                    "polygraphml.engine.compute_child",
                    str(request_path),
                    str(result_path),
                ],
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                return_code = process.wait(timeout=self.wall_timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise PolygraphError(
                    "EXECUTION_TIMEOUT",
                    "Bounded model evaluation exceeded its wall-clock limit.",
                    detail={"limit_seconds": self.wall_timeout_seconds},
                ) from exc
            if not result_path.is_file() or result_path.stat().st_size > MAX_RESULT_BYTES:
                raise PolygraphError(
                    "EXECUTION_FAILED", "Bounded model evaluation returned no valid result."
                )
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PolygraphError(
                    "EXECUTION_FAILED", "Bounded model evaluation returned malformed output."
                ) from exc
            if return_code != 0:
                code = str(payload.get("code", "EXECUTION_FAILED"))
                message = str(payload.get("message", "Bounded model evaluation failed."))
                raise PolygraphError(code, message)
            try:
                return ComputeResult.model_validate(payload)
            except ValueError as exc:
                raise PolygraphError(
                    "EXECUTION_FAILED", "Bounded model evaluation returned an invalid schema."
                ) from exc
