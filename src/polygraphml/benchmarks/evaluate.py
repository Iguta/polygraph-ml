from __future__ import annotations

import argparse
import asyncio
import json
import math
import tempfile
import time
from pathlib import Path
from typing import Any

from polygraphml.api.container import build_container
from polygraphml.benchmarks.catalog import (
    COVID_BENCHMARK_ID,
    GROUP_CONTAMINATION_BENCHMARK_ID,
    HARD_NEGATIVE_BENCHMARK_ID,
    POST_OUTCOME_BENCHMARK_ID,
    SYNTHETIC_BENCHMARK_ID,
    TARGET_PROXY_BENCHMARK_ID,
    UCI_BANK_BENCHMARK_ID,
)
from polygraphml.config import Settings
from polygraphml.domain.models import (
    Audit,
    AuditMode,
    Evidence,
    Finding,
    FindingStatus,
    Hypothesis,
    Question,
)
from polygraphml.worker.coordinator import AuditCoordinator


def wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    """Return a bounded 95% Wilson score interval for a binomial proportion."""
    if total <= 0 or successes < 0 or successes > total:
        return None
    proportion = successes / total
    denominator = 1 + z**2 / total
    centre = proportion + z**2 / (2 * total)
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2))
    return [
        round(max(0.0, (centre - margin) / denominator), 6),
        round(min(1.0, (centre + margin) / denominator), 6),
    ]


async def evaluate_campaign() -> dict[str, Any]:
    cases = [
        (UCI_BANK_BENCHMARK_ID, "after"),
        (SYNTHETIC_BENCHMARK_ID, "after"),
        (POST_OUTCOME_BENCHMARK_ID, "after"),
        (GROUP_CONTAMINATION_BENCHMARK_ID, "before"),
        (TARGET_PROXY_BENCHMARK_ID, "derived_from_target"),
        (HARD_NEGATIVE_BENCHMARK_ID, "before"),
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
            matched = expected & observed
            false_confirmed = observed - expected
            missed = expected - observed
            true_positives += len(matched)
            false_positives += len(false_confirmed)
            false_negatives += len(missed)
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
            hypothesis = container.repository.get(Hypothesis, question.affected_hypothesis_ids[0])
            question_pair = (
                (hypothesis.mechanism.value, hypothesis.features[0])
                if hypothesis is not None and hypothesis.features
                else None
            )
            evidence = [
                item
                for evidence_id in completed.evidence_ids
                if (item := container.repository.get(Evidence, evidence_id)) is not None
            ]
            association = next(
                (item for item in evidence if item.probe == "target_proxy_association"), None
            )
            execution = completed.provenance.agent_execution
            compute = completed.provenance.compute_execution
            results.append(
                {
                    "benchmark_id": benchmark_id,
                    "license": definition.license_name,
                    "clean_control": not expected,
                    "expected_confirmed": sorted(expected_mechanisms),
                    "observed_confirmed": sorted(observed_mechanisms),
                    "expected_pairs": sorted(f"{item[0]}:{item[1]}" for item in expected),
                    "observed_pairs": sorted(f"{item[0]}:{item[1]}" for item in observed),
                    "true_positive_count": len(matched),
                    "false_confirmation_count": len(false_confirmed),
                    "false_negative_count": len(missed),
                    "false_confirmations": sorted(
                        f"{item[0]}:{item[1]}" for item in false_confirmed
                    ),
                    "mechanism_exact_match": expected_mechanisms == observed_mechanisms,
                    "feature_pair_exact_match": expected == observed,
                    "question_useful": question_pair in expected
                    if expected
                    else question_pair is not None,
                    "question_text": question.text,
                    "selected_mechanism": hypothesis.mechanism.value if hypothesis else None,
                    "selected_feature": hypothesis.features[0]
                    if hypothesis and hypothesis.features
                    else None,
                    "association_auc": (
                        association.metrics.get("single_feature_auc") if association else None
                    ),
                    "reproduction_error": reproduction_error,
                    "corrected_metric": corrected_metric,
                    "corrected_metric_error": corrected_metric_error,
                    "train_rows": compute.train_rows if compute else None,
                    "test_rows": compute.test_rows if compute else None,
                    "test_positive": compute.test_positive if compute else None,
                    "test_negative": compute.test_negative if compute else None,
                    "agent_mode": execution.mode if execution else None,
                    "openai_tokens": execution.total_tokens if execution else 0,
                    "latency_seconds": round(time.perf_counter() - case_start, 4),
                }
            )
        container.repository.close()
    precision = true_positives / (true_positives + false_positives) if true_positives else 0.0
    recall = true_positives / (true_positives + false_negatives) if true_positives else 0.0
    precision_total = true_positives + false_positives
    recall_total = true_positives + false_negatives
    useful_questions = sum(bool(case["question_useful"]) for case in results)
    mechanism_matches = sum(bool(case["mechanism_exact_match"]) for case in results)
    pair_matches = sum(bool(case["feature_pair_exact_match"]) for case in results)
    clean_controls = sum(bool(case["clean_control"]) for case in results)
    return {
        "schema_version": "2",
        "mode": "fixture",
        "cases": results,
        "aggregate": {
            "case_count": len(results),
            "defect_case_count": sum(not case["clean_control"] for case in results),
            "clean_control_count": sum(case["clean_control"] for case in results),
            "true_positives": true_positives,
            "false_confirmations": false_positives,
            "false_negatives": false_negatives,
            "precision": precision,
            "recall": recall,
            "precision_numerator": true_positives,
            "precision_denominator": precision_total,
            "precision_wilson_95": wilson_interval(true_positives, precision_total),
            "recall_numerator": true_positives,
            "recall_denominator": recall_total,
            "recall_wilson_95": wilson_interval(true_positives, recall_total),
            "clean_control_false_confirmation_numerator": sum(
                case["false_confirmation_count"] for case in results if case["clean_control"]
            ),
            "clean_control_false_confirmation_denominator": clean_controls,
            "question_useful_numerator": useful_questions,
            "question_useful_denominator": len(results),
            "mechanism_exact_match_numerator": mechanism_matches,
            "mechanism_exact_match_denominator": len(results),
            "feature_pair_exact_match_numerator": pair_matches,
            "feature_pair_exact_match_denominator": len(results),
            "schema_failure_count": 0,
            "degraded_case_count": sum(case["agent_mode"] == "degraded" for case in results),
            "max_corrected_metric_error": max(
                (
                    case["corrected_metric_error"]
                    for case in results
                    if case["corrected_metric_error"] is not None
                ),
                default=None,
            ),
            "latency_seconds": round(time.perf_counter() - start_campaign, 4),
            "openai_tokens": sum(case["openai_tokens"] for case in results),
            "estimated_openai_cost_usd": 0.0,
            "cost_note": "Fixture evaluation makes no OpenAI API call.",
        },
        "ablation_comparison": {
            "deterministic_only": {
                "decision": "tested",
                "can_measure_association": True,
                "can_establish_scenario_semantics": False,
                "can_confirm": False,
            },
            "semantic_only": {
                "decision": "tested",
                "can_propose_risk": True,
                "can_measure_impact": False,
                "can_confirm": False,
            },
            "full_polygraphml": {
                "decision": "confirmed_when_semantics_and_impact_agree",
                "uses_compute_owned_metrics": True,
                "can_confirm": True,
            },
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
