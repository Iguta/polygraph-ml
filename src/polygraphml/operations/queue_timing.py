from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polygraphml.config import Settings


class QueueTimingReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    measurement_mode: Literal["fixture", "live"]
    case_count: int = Field(ge=1)
    observed_max_seconds: float = Field(ge=0)
    observed_p95_seconds: float = Field(ge=0)
    startup_allowance_seconds: int = Field(ge=0)
    safety_multiplier: float = Field(ge=1)
    recommended_visibility_seconds: int = Field(ge=1, le=43_200)
    configured_visibility_seconds: int = Field(ge=1, le=43_200)
    configured_heartbeat_seconds: float = Field(gt=0)
    configured_covers_measurement: bool
    production_calibrated: bool
    limitations: list[str]


def heartbeat_interval_seconds(visibility_seconds: int) -> float:
    return max(1.0, min(60.0, visibility_seconds / 3))


def recommend_queue_timing(
    durations: list[float],
    *,
    measurement_mode: Literal["fixture", "live"],
    configured_visibility_seconds: int,
    startup_allowance_seconds: int = 30,
    safety_multiplier: float = 4.0,
) -> QueueTimingReport:
    if not durations or any(duration < 0 for duration in durations):
        raise ValueError("At least one non-negative duration is required.")
    ordered = sorted(durations)
    p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    observed_p95 = ordered[p95_index]
    recommendation = min(
        43_200,
        max(
            60,
            math.ceil(observed_p95 * safety_multiplier + startup_allowance_seconds),
        ),
    )
    production_calibrated = measurement_mode == "live" and len(durations) >= 20
    limitations = []
    if not production_calibrated:
        limitations.append(
            "Production calibration requires at least 20 deployed live audit durations."
        )
    return QueueTimingReport(
        measurement_mode=measurement_mode,
        case_count=len(durations),
        observed_max_seconds=max(ordered),
        observed_p95_seconds=observed_p95,
        startup_allowance_seconds=startup_allowance_seconds,
        safety_multiplier=safety_multiplier,
        recommended_visibility_seconds=recommendation,
        configured_visibility_seconds=configured_visibility_seconds,
        configured_heartbeat_seconds=heartbeat_interval_seconds(configured_visibility_seconds),
        configured_covers_measurement=configured_visibility_seconds >= recommendation,
        production_calibrated=production_calibrated,
        limitations=limitations,
    )


def report_from_benchmark(path: Path, configured_visibility_seconds: int) -> QueueTimingReport:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    mode = payload.get("mode")
    if mode not in {"fixture", "live"}:
        raise ValueError("Benchmark mode must be fixture or live.")
    cases = payload.get("cases", [])
    runs = payload.get("runs", [])
    durations = [
        float(case["latency_seconds"])
        for case in cases
        if isinstance(case, dict) and "latency_seconds" in case
    ]
    if not durations:
        durations = [
            float(run["duration_seconds"])
            for run in runs
            if isinstance(run, dict) and "duration_seconds" in run
        ]
    return recommend_queue_timing(
        durations,
        measurement_mode=mode,
        configured_visibility_seconds=configured_visibility_seconds,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive SQS visibility and heartbeat evidence from captured audit durations."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--configured-visibility-seconds",
        type=int,
        default=Settings().worker_lease_seconds,
    )
    arguments = parser.parse_args()
    report = report_from_benchmark(arguments.input, arguments.configured_visibility_seconds)
    rendered = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
