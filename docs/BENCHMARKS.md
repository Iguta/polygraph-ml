# Benchmark Evaluation

PolygraphML's release gate audits a model, dataset, notebook, and scenario together. Expectations are declared in the benchmark registry before execution, and the evaluator writes machine-readable evidence to [`benchmark-results/latest.json`](../benchmark-results/latest.json).

## Included cases

| ID | Evidence bundle | Purpose | Expected confirmed findings |
|---|---|---|---|
| `synthetic_campaign_leak_v1` | Generated CSV, `.skops` logistic-regression model, and executed notebook | Multi-mechanism planted failure | `post_outcome`, `group_contamination` |
| `synthetic_post_outcome_only_v1` | Campaign bundle with unique-entity mapping | Isolated mechanism | `post_outcome` |
| `synthetic_group_contamination_only_v1` | Campaign bundle with pre-decision availability answer | Isolated mechanism | `group_contamination` |
| `uci_covid_surveillance_clean_v1` | Pinned UCI COVID-19 Surveillance CSV snapshot, generated `.skops` model, and reproducible notebook | Public clean control | None |

The UCI source is versioned as `uci-2020+polygraphml-1.0.0`, licensed CC BY 4.0, and identified by DOI `10.24432/C5TC85`. The embedded source snapshot has a declared SHA-256 hash in the registry. This 14-row teaching dataset is used only to exercise provenance, reproduction, and false-confirmation behavior. It does not validate a clinical diagnostic system.

## Captured fixture result

The current checked-in result records:

- confirmed-finding precision `1.0` and recall `1.0` across four expected confirmations;
- zero false confirmations and zero false negatives;
- zero reproduction error for all four cases;
- campaign corrected ROC AUC `0.8627956989247312` and corrected-metric error `0.0`;
- zero OpenAI tokens and `$0.00` estimated OpenAI cost because this is explicitly a fixture run.

Latency is captured on each run and is machine-dependent. It is evidence about the deterministic fixture gate, not a claim about deployed or live-model latency.

## Run the gate

```bash
uv run polygraphml-benchmarks --output benchmark-results/latest.json
uv run polygraphml-queue-calibration --input benchmark-results/latest.json --output benchmark-results/queue-timing.json
uv run pytest tests/test_benchmark_evaluation.py
```

Fixture results must never be presented as a live GPT-5.6 evaluation. A separate sanitized live trace is still required before the live-agent DoD can be checked.

The checked-in queue-timing artifact records four fixture cases, observed p95 `0.0755` seconds, a 60-second evidence-based minimum, and the configured 300-second visibility timeout with a 60-second heartbeat. It remains explicitly uncalibrated for production until at least 20 deployed live durations are captured.

## Admission rules

A new benchmark needs source and license metadata, immutable hashes or a deterministic generation specification, an artifact manifest, a complete scenario, predeclared expectations, metric tolerance, and prohibited claims. Clean cases are release-blocking if they produce a false confirmed finding.
