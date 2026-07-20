from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from polygraphml.api.container import build_container
from polygraphml.benchmarks.catalog import (
    COVID_BENCHMARK_ID,
    GROUP_CONTAMINATION_BENCHMARK_ID,
    POST_OUTCOME_BENCHMARK_ID,
    SYNTHETIC_BENCHMARK_ID,
)
from polygraphml.config import Settings
from polygraphml.domain.models import Audit, AuditMode, Finding, FindingStatus, Question
from polygraphml.worker.coordinator import AuditCoordinator


async def evaluate_campaign() -> dict[str, Any]:
    cases = [
        (SYNTHETIC_BENCHMARK_ID, "after"),
        (POST_OUTCOME_BENCHMARK_ID, "after"),
        (GROUP_CONTAMINATION_BENCHMARK_ID, "before"),
        (COVID_BENCHMARK_ID, "before"),
    ]
    results: list[dict[str, Any]] = []
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    start_campaign = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="polygraphml-benchmark-") as temporary:
        root = Path(temporary)
        settings = Settings(
            environment="test",
            agent_mode="fixture",
            database_path=root / "state.db",
            artifact_root=root / "artifacts",
            worker_lease_seconds=30,
        )
        container = build_container(settings)
        coordinator = AuditCoordinator(
            settings, container.repository, container.artifacts, container.queue
        )
        for index, (benchmark_id, answer) in enumerate(cases):
            session, _ = container.repository.create_session(3600)
            definition = container.benchmarks.get(benchmark_id)
            case_start = time.perf_counter()
            project = container.projects.create_benchmark_project(session, benchmark_id)
            audit = container.audits.start(
                session,
                project,
                1,
                AuditMode.COMPLETE,
                f"benchmark-start-{index}",
            )
            job = container.queue.receive()
            if job is None:
                raise RuntimeError("Benchmark start job was not queued.")
            await coordinator.process(job)
            waiting = container.repository.get(Audit, audit.audit_id)
            if waiting is None or not waiting.question_ids:
                raise RuntimeError("Benchmark did not reach its declared human checkpoint.")
            question = container.repository.get(Question, waiting.question_ids[-1])
            if question is None:
                raise RuntimeError("Benchmark question was not persisted.")
            container.audits.answer(
                session,
                waiting,
                question,
                answer,
                f"benchmark-answer-{index}",
            )
            resume = container.queue.receive()
            if resume is None:
                raise RuntimeError("Benchmark resume job was not queued.")
            await coordinator.process(resume)
            completed = container.repository.get(Audit, audit.audit_id)
            if completed is None or completed.status.value != "complete":
                raise RuntimeError("Benchmark did not complete.")
            findings = [
                finding
                for finding_id in completed.finding_ids
                if (finding := container.repository.get(Finding, finding_id)) is not None
            ]
            expected = {
                (expectation.mechanism.value, expectation.feature)
                for expectation in definition.expectations
                if expectation.expected_status == FindingStatus.CONFIRMED
            }
            observed = {
                (finding.mechanism.value, finding.features[0] if finding.features else "")
                for finding in findings
                if finding.status == FindingStatus.CONFIRMED
            }
            expected_mechanisms = {mechanism for mechanism, _ in expected}
            observed_mechanisms = {mechanism for mechanism, _ in observed}
            true_positives += len(expected_mechanisms & observed_mechanisms)
            false_positives += len(observed_mechanisms - expected_mechanisms)
            false_negatives += len(expected_mechanisms - observed_mechanisms)
            comparison = completed.metric_comparison
            reproduction_error = None
            if comparison and comparison.reported and comparison.reproduced:
                reproduction_error = abs(comparison.reported.value - comparison.reproduced.value)
            corrected_metric = (
                comparison.corrected.value
                if comparison is not None and comparison.corrected is not None
                else None
            )
            corrected_metric_error = (
                abs(corrected_metric - definition.expected_corrected_metric)
                if corrected_metric is not None and definition.expected_corrected_metric is not None
                else None
            )
            results.append(
                {
                    "benchmark_id": benchmark_id,
                    "license": definition.license_name,
                    "expected_confirmed": sorted(expected_mechanisms),
                    "observed_confirmed": sorted(observed_mechanisms),
                    "false_confirmations": sorted(observed_mechanisms - expected_mechanisms),
                    "reproduction_error": reproduction_error,
                    "corrected_metric": corrected_metric,
                    "corrected_metric_error": corrected_metric_error,
                    "latency_seconds": round(time.perf_counter() - case_start, 4),
                }
            )
        container.repository.close()
    precision = true_positives / (true_positives + false_positives) if true_positives else 0.0
    recall = true_positives / (true_positives + false_negatives) if true_positives else 0.0
    return {
        "schema_version": "1",
        "mode": "fixture",
        "cases": results,
        "aggregate": {
            "true_positives": true_positives,
            "false_confirmations": false_positives,
            "false_negatives": false_negatives,
            "precision": precision,
            "recall": recall,
            "max_corrected_metric_error": max(
                (
                    case["corrected_metric_error"]
                    for case in results
                    if case["corrected_metric_error"] is not None
                ),
                default=None,
            ),
            "latency_seconds": round(time.perf_counter() - start_campaign, 4),
            "openai_tokens": 0,
            "estimated_openai_cost_usd": 0.0,
            "cost_note": "Fixture evaluation makes no OpenAI API call.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the deterministic PolygraphML benchmark gate."
    )
    parser.add_argument("--output", type=Path, help="Optional JSON result path.")
    arguments = parser.parse_args()
    result = asyncio.run(evaluate_campaign())
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
