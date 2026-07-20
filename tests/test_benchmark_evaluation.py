from __future__ import annotations

from polygraphml.benchmarks.evaluate import evaluate_campaign


async def test_release_benchmark_gate_has_no_false_confirmations() -> None:
    result = await evaluate_campaign()
    aggregate = result["aggregate"]
    assert aggregate["precision"] == 1.0
    assert aggregate["recall"] == 1.0
    assert aggregate["true_positives"] == 4
    assert aggregate["false_confirmations"] == 0
    assert aggregate["openai_tokens"] == 0
    assert aggregate["max_corrected_metric_error"] == 0.0
    campaign = next(
        case for case in result["cases"] if case["benchmark_id"] == "synthetic_campaign_leak_v1"
    )
    assert campaign["corrected_metric_error"] == 0.0
    post_outcome = next(
        case for case in result["cases"] if case["benchmark_id"] == "synthetic_post_outcome_only_v1"
    )
    assert post_outcome["observed_confirmed"] == ["post_outcome"]
    group_contamination = next(
        case
        for case in result["cases"]
        if case["benchmark_id"] == "synthetic_group_contamination_only_v1"
    )
    assert group_contamination["observed_confirmed"] == ["group_contamination"]
    covid = next(
        case
        for case in result["cases"]
        if case["benchmark_id"] == "uci_covid_surveillance_clean_v1"
    )
    assert covid["observed_confirmed"] == []
    assert covid["license"] == "CC BY 4.0"
