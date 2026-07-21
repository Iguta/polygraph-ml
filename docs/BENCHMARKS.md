# Benchmark Evaluation

PolygraphML's release gate audits a model, dataset, notebook, and scenario together. Expectations and prohibited claims live in the benchmark registry before a live run. The evaluator writes machine-readable, fixture-labeled evidence to [`benchmark-results/latest.json`](../benchmark-results/latest.json).

## Included cases

| ID | Evidence bundle | Purpose | Expected confirmed pair(s) |
|---|---|---|---|
| `uci_bank_marketing_duration_v1` | Full 45,211-row UCI Bank Marketing derived table, `.skops` model, executed notebook, derivation record | Flagship public semantic proof | `post_outcome:duration` |
| `synthetic_campaign_leak_v1` | Generated CSV, `.skops` model, executed notebook | Multi-mechanism planted failure | `post_outcome:call_duration`, `group_contamination:household_id` |
| `synthetic_post_outcome_only_v1` | Campaign bundle with unique-entity mapping | Isolated mechanism | `post_outcome:call_duration` |
| `synthetic_group_contamination_only_v1` | Campaign bundle with pre-decision answer | Isolated automatic probe | `group_contamination:household_id` |
| `synthetic_semantic_proxy_v1` | Innocuous feature name with separately declared provenance | Semantic target proxy | `target_proxy:engagement_band` |
| `synthetic_suspicious_hard_negative_v1` | Highly predictive previous-call duration documented as pre-decision | Hard negative: association must not accuse | None |
| `uci_covid_surveillance_clean_v1` | Pinned 14-row UCI source snapshot, generated `.skops` model, notebook | Public adapter/provenance clean control | None |

The flagship source is UCI Bank Marketing, DOI `10.24432/C5K306`, CC BY 4.0. `derivation.txt` records the outer archive, inner archive, and source CSV hashes plus the deterministic mapping/split recipe. `.polygraphml.yml` pins every shipped artifact hash and describes `duration` as the current contact duration without encoding the expected finding.

The COVID source is UCI COVID-19 Surveillance, DOI `10.24432/C5TC85`, CC BY 4.0. Its 14 rows make it a useful clean adapter/provenance smoke case, not clinical validation.

## Captured fixture result — July 21, 2026

The checked-in schema-v2 result records:

- seven cases: five defect cases and two clean controls;
- six expected/observed feature-mechanism pairs, zero false confirmations, and zero false negatives;
- precision and recall `6/6 = 1.0`, with 95% Wilson intervals `[0.609657, 1.0]`—the interval makes the small sample explicit;
- exact mechanism and feature-pair matches in `7/7` cases;
- useful material questions in `6/7` cases; the group-only defect is found by the automatic deterministic probe rather than the semantic question;
- zero schema failures, zero degraded cases, zero OpenAI tokens, and `$0.00` fixture-model cost;
- two clean controls with `0/2` false confirmations;
- flagship reported ROC AUC `0.871301`, reproduced ROC AUC `0.8713005400607956`, and corrected ROC AUC `0.7330845871361364` after removing current-call `duration`;
- semantic-proxy corrected ROC AUC `0.8145254629629629`;
- aggregate machine-dependent fixture runtime is recorded in the result rather than treated as a stable benchmark score.

Association is not used as semantic proof. The hard negative's held-out single-feature AUC is `0.9172043010752688`, yet it has no confirmed finding because its scenario establishes availability before the decision. The flagship's association AUC is `0.8050363796447461`; confirmation additionally requires the timing answer and measured correction.

## Run the gates

```bash
make benchmarks
make calibrate-queue
uv run pytest tests/test_benchmark_evaluation.py
```

Fixture output must never be presented as live GPT-5.6 evaluation. The only release-authorized live sweep is:

```bash
make eval-live
```

That command performs exactly one live call for each of the flagship, semantic proxy, and hard negative, with at most five agent turns per call. The first failed run is preserved at `benchmark-results/live-evaluation.json`; an explicitly approved repaired run writes sanitized metadata to `benchmark-results/live-evaluation-rerun.json`. The evaluator refuses to overwrite either record. Do not rerun or broaden it without explicit cost approval.

The first authorized v0.2 run completed all three cases on July 21 and failed the release gate honestly. The flagship live plan independently selected `post_outcome:duration` and a material question, but its free-form answer option was not recognized by the deterministic availability parser, so no confirmation was emitted. The semantic-proxy run selected `engagement_band` but classified it as `post_outcome`, not `target_proxy`. The hard negative visibly degraded with `MODEL_OUTPUT_INVALID`, while deterministic evidence still cleared it. The preserved record contains 6,825 total tokens and 43,860 ms of agent latency, no payloads, no sensitive data, and no raw chain-of-thought.

After explicit approval, the repaired gate ran exactly once and passed all three cases. GPT-5.6 Sol selected and confirmed `post_outcome:duration`, selected and confirmed `target_proxy:engagement_band`, and selected then cleared `post_outcome:previous_call_duration` without a false confirmation. All cases were live with no failure code or degradation; each question was material; each audit reached `complete`; and the sanitized record contains 10,774 total tokens, 65,408 ms aggregate agent latency, and six typed tool-result events. `benchmark-results/live-evaluation-rerun.json` stores no payloads, sensitive traces, or raw chain-of-thought and has SHA-256 `aea0d4a8eae05d6876cf27e25e964ffaca7722a447ca801892ca86d6f85a413c`.

`benchmark-results/queue-timing.json` is fixture-only timing evidence: seven cases, P95/max `4.0768` seconds, a 60-second minimum recommendation, and an explicit production-calibration limitation. The prior deployed slice has a separate 20-run live timing record in `queue-timing-live.json` (P95 `32.666` seconds, 161-second recommendation); it is historical evidence and must be recalibrated after deploying the larger flagship workload.

## Public GitHub gate

The root manifest and artifacts passed local import/contract tests and the public gate at immutable reviewed candidate `4925f8a4ba28fb06f96277bdb4b1ccc002f969b6`. The expected findings were already committed at `16dd4c659f4f7f36507d40ff60fbc9280cb82cc5`, before the first live evaluation. A local repository path or mutable branch would not have satisfied this gate.

```bash
REF=<40-character-commit-sha> make public-github-gate
```

The command fails unless GitHub resolves the exact requested commit, the root manifest and all declared hashes validate, the flagship audit completes after its material question, the expected `post_outcome:duration` pair is confirmed, and all reported/reproduced/corrected metric values exist. Its metadata-only result is written to `benchmark-results/public-github-gate.json`.

## Admission rules

A new benchmark needs source and license metadata, immutable hashes or a deterministic generation specification, a strict artifact manifest, a complete scenario, predeclared expectations, metric tolerance, limitations, and prohibited claims. Clean cases are release-blocking if they produce a false `confirmed` finding. Expected output is never changed after a failure merely to make the gate green.
