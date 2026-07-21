from __future__ import annotations

from polygraphml.benchmarks.evaluate import evaluate_campaign, wilson_interval


def test_wilson_interval_reports_uncertainty_and_rejects_invalid_counts() -> None:
    assert wilson_interval(6, 6) == [0.609657, 1.0]
    assert wilson_interval(0, 2) == [0.0, 0.657628]
    assert wilson_interval(1, 0) is None
    assert wilson_interval(3, 2) is None


async def test_release_benchmark_gate_has_no_false_confirmations() -> None:
    result = await evaluate_campaign()
    aggregate = result["aggregate"]
    assert result["schema_version"] == "2"
    assert aggregate["case_count"] == 7
    assert aggregate["clean_control_count"] == 2
    assert aggregate["precision"] == 1.0
    assert aggregate["recall"] == 1.0
    assert aggregate["true_positives"] == 6
    assert aggregate["false_confirmations"] == 0
    assert aggregate["openai_tokens"] == 0
    assert aggregate["max_corrected_metric_error"] == 0.0
    assert aggregate["precision_numerator"] == 6
    assert aggregate["precision_denominator"] == 6
    assert aggregate["precision_wilson_95"] == [0.609657, 1.0]
    assert aggregate["question_useful_numerator"] == 6
    assert aggregate["feature_pair_exact_match_numerator"] == 7
    assert aggregate["schema_failure_count"] == 0
    assert aggregate["degraded_case_count"] == 0
    campaign = next(
        case for case in result["cases"] if case["benchmark_id"] == "synthetic_campaign_leak_v1"
    )
    assert campaign["corrected_metric_error"] == 0.0
    flagship = next(
        case for case in result["cases"] if case["benchmark_id"] == "uci_bank_marketing_duration_v1"
    )
    assert flagship["selected_feature"] == "duration"
    assert flagship["observed_confirmed"] == ["post_outcome"]
    assert flagship["corrected_metric_error"] == 0.0
    assert flagship["train_rows"] == 32551
    assert flagship["test_rows"] == 12660
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
    target_proxy = next(
        case for case in result["cases"] if case["benchmark_id"] == "synthetic_semantic_proxy_v1"
    )
    assert target_proxy["observed_confirmed"] == ["target_proxy"]
    assert target_proxy["association_auc"] == 1.0
    hard_negative = next(
        case
        for case in result["cases"]
        if case["benchmark_id"] == "synthetic_suspicious_hard_negative_v1"
    )
    assert hard_negative["observed_confirmed"] == []
    assert hard_negative["false_confirmation_count"] == 0
    assert hard_negative["predeclared_question_pairs"] == ["post_outcome:previous_call_duration"]
    assert hard_negative["question_useful"] is True
    covid = next(
        case
        for case in result["cases"]
        if case["benchmark_id"] == "uci_covid_surveillance_clean_v1"
    )
    assert covid["observed_confirmed"] == []
    assert covid["license"] == "CC BY 4.0"
    assert covid["predeclared_question_pairs"] == ["post_outcome:A07"]
    assert covid["question_useful"] is True
    assert result["ablation_comparison"]["deterministic_only"]["can_confirm"] is False
