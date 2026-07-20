# Technical Design Document — PolygraphML

**Version:** 1.1 · **Owner:** David · **Date:** July 18, 2026 · **Status:** Approved foundation

## 1. Overview

PolygraphML is an asynchronous React/FastAPI application that audits a trained model, evaluation data, and its training/evaluation pipeline as one evidence bundle. A single GPT-5.6 Sol agent plans and interprets the investigation; versioned Python tools reconstruct metrics, test hypotheses, and apply corrections.

The central invariant is:

> **The model reasons; code computes; evidence decides.**

The product must distinguish a semantic suspicion from a confirmed defect, an ablation impact from leakage proof, and a model reasoning summary from independently computed evidence.

## 2. Domain model

| Entity | Responsibility |
|---|---|
| `Project` | Submission container, source type, pinned repository commit, retention policy |
| `Artifact` | Dataset, model, notebook, code, manifest, checksum, media type, adapter status |
| `Scenario` | Target, entity, decision time, horizon, split unit, metric, user assumptions |
| `Audit` | Durable state machine, evaluator/model versions, status, result references |
| `Question` | Material ambiguity, choices/free-text answer, blocking state, affected hypotheses |
| `Hypothesis` | Suspected mechanism, assumptions, rationale summary, requested probe, falsifier |
| `Evidence` | Deterministic observation with tool version, inputs, outputs, and provenance |
| `Finding` | Lifecycle and conclusion tying hypotheses to evidence and correction |
| `MetricComparison` | Reported, reproduced, and corrected metrics with protocol and tolerance |
| `AuditEvent` | Ordered, sanitized Decision Trace record |
| `Report` | Technical or stakeholder rendering of immutable audit results |

Full transport shapes are defined in [API_CONTRACT.md](API_CONTRACT.md).

## 3. Audit state machine

```text
draft
  → validating
  → queued
  → reconstructing
  → reproducing
  → interrogating
  → waiting_for_user ──answer──┐
  → probing ◀──────────────────┘
  → correcting
  → composing
  → complete
```

Any running state may transition to `failed_partial` when useful evidence exists or `failed` when intake prevents analysis. Transitions use conditional writes so duplicate SQS delivery cannot move an audit backward or repeat a committed correction.

## 4. Intake and artifact adapters

### Repository importer

Accept a public GitHub URL and optional ref, resolve it to a commit SHA, enforce size/path limits, inventory files, and locate candidate notebooks, manifests, datasets, and models. Static inspection is always separate from execution.

### Dataset adapters

Initial adapters read CSV and Parquet, infer schema, summarize values, and expose chunked access. Profiles include row count, types, missingness, cardinality, samples, distribution sketches, target balance, entity/time coverage, and checksum. Raw rows are not sent to the model by default.

### Model adapters

- `SkopsAdapter`: supported scikit-learn estimators and preprocessing objects after type inspection.
- `XGBoostInspector`: `.json` receives structural validation; `.ubj` is recognized but remains a limited/P1 execution path.
- `OnnxDescriptor`: recognizes ONNX evidence and labels it limited; inference equivalence is P1 and requires explicit preprocessing metadata.
- `UnsupportedAdapter`: preserves metadata and reason so partial notebook/repository auditing can continue.

Arbitrary JSON is never assumed to be a model. Pickle, joblib, and cloudpickle are denied at validation.

### Notebook/pipeline parser

Parse `.ipynb` and Python source without executing it to identify imports, data reads, split calls, preprocessing fit/transform order, training calls, metric calculations, printed claims, seeds, and source locations. A `polygraphml.yaml` manifest can resolve ambiguity but cannot override security policy.

## 5. Scenario and follow-up questions

The `Scenario` is part of the audit input, not report decoration. Before confirming an availability or temporal finding, the agent must know—or explicitly mark unknown—the decision point and prediction horizon. Questions are emitted only when the answer could change the investigation.

The agent returns a structured `QuestionRequest` containing:

- concise question;
- why it matters;
- affected hypotheses;
- expected answer type;
- safe default, if any;
- whether the audit can continue in parallel.

Answers are immutable events. Any revised answer creates a new scenario revision and triggers reevaluation of affected findings.

## 6. Agent design

The MVP uses one `AuditAgent` implemented with the OpenAI Agents SDK and explicitly configured with `gpt-5.6-sol`. Its initial typed, read-only tools cover:

- artifact and scenario inspection;
- sanitized dataset-profile inspection;
- static notebook-summary inspection;
- supported-probe discovery.

The structured plan can request a supported probe and propose one question, while application code owns probe execution, correction, finding transitions, and reports. P0 validates that the primary live hypothesis is `post_outcome`, requests `feature_availability`, and names only a feature from reconstructed model feature order; unsupported output degrades visibly instead of being reinterpreted. The agent cannot write metric values directly. Structured model outputs are validated and bounded by a five-turn limit; a failure degrades to the deterministic fixture plan with an explicit warning event.

No multi-agent handoffs are required for the MVP. A second agent is justified only if benchmark evaluation demonstrates a measurable quality, latency, or maintainability improvement.

## 7. Reproduction engine

The engine seeks the closest safe reproduction tier:

1. **Exact supported reconstruction:** safe adapter plus parsed evaluation protocol can rerun the submitted model.
2. **Controlled pipeline reconstruction:** PolygraphML rebuilds the split/preprocessing/evaluation from declared evidence.
3. **Reference challenger:** when the user artifact cannot run, a versioned baseline estimates dataset-level effects without pretending to reproduce the submitted model.
4. **Static-only review:** code and scenario issues are reported, but metric reproduction is marked unavailable.

The tier is visible in every metric comparison. Reproducibility captures source commit, artifact hashes, library versions, seed, split indices or hashes, feature order, and evaluator version.

## 8. Deterministic probe suite

| Probe | Evidence | Initial method |
|---|---|---|
| Reported metric extraction | Claim and source location | Notebook output/AST/manifest parsing |
| Metric reconstruction | Reproduced score and tolerance | Versioned evaluator on preserved split |
| Single-feature power | Held-out predictive signal | Ablation/correction on the reconstructed model; broader univariate probes are P1 |
| Exact duplication | Cross-split overlap | Stable row hashes |
| Group contamination | Entity overlap | Group IDs across split membership |
| Post-outcome availability | Feature unavailable at decision time | Scenario answer plus feature correction |
| Temporal backtesting | Future-window contamination | P1; surfaced as an unsupported limitation |
| Target proxy | Implausible target association | P1; surfaced as an unsupported limitation |
| Preprocessing leakage | Fit before split/fold | Static pipeline inspection and reconstructed comparison |
| Ablation | Model reliance and impact | Reevaluate/retrain without suspect feature set |
| Corrected evaluation | Honest protocol result | Smallest justified split/preprocessing/feature repair |

Thresholds are configuration and benchmark data, not universal truths. Probe output includes limitations and cannot promote a finding by itself unless the finding policy explicitly allows it.

## 9. Finding policy

Statuses are `needs_context`, `suspected`, `tested`, `confirmed`, `cleared`, and `inconclusive`.

A finding may become `confirmed` only when:

1. the scenario and mechanism are sufficiently established;
2. at least one deterministic evidence item supports the mechanism;
3. the impact is measured on a valid evaluation protocol, or the finding type is intrinsically protocol-invalidating and the limitation is stated;
4. contradictory evidence is recorded and resolved;
5. the conclusion states what could change it.

A large ablation delta establishes model reliance, not necessarily leakage. A small delta can still reveal a real defect with limited aggregate impact. Severity, confidence, and status are separate fields.

## 10. Decision Trace

The user-visible trace is an application-owned event log, not a mirror of private model state. Event types include:

`audit_state`, `assumption`, `question`, `answer`, `hypothesis`, `tool_started`, `tool_result`, `evidence`, `correction`, `finding_changed`, `reasoning_summary`, `warning`, `retry`, `error`, and `verdict`.

Each event includes event ID, audit ID, monotonic sequence, timestamp, actor (`user`, `agent`, `tool`, `system`), public payload, and provenance references. Developer traces may contain additional operational data but are sanitized independently and are not exposed directly to users.

## 11. Queue, persistence, and idempotency

The API writes an audit as `enqueue_pending` before enqueueing. An SQS message contains `audit_id`, operation, schema version, and idempotency key. If the queue send or API process fails between those steps, an idempotent retry and the worker's bounded stale-queued-audit reconciler re-enqueue the durable audit. The worker acquires a conditional lease in DynamoDB, checkpoints after each committed step, extends visibility while active, and deletes the message only after a terminal or intentionally paused checkpoint.

Question pauses do not hold an SQS message indefinitely. The worker persists `waiting_for_user`, releases the job, and an answer enqueues a resume operation. Exhausted retryable failures enter the DLQ and raise an operational alarm.

Artifacts and large results live in S3. DynamoDB stores metadata, current state, ordered events, and immutable references. S3 object keys are content- or audit-addressed so retries do not create divergent outputs.

## 12. Security design

- API and coordinator containers never load remote pickle-like objects.
- The OpenAI key is read from Secrets Manager only by the coordinator role.
- Submitted code, if execution is enabled, runs in a separate disposable task with no secrets and restricted egress.
- Presigned URLs are short-lived, scoped to one project prefix, and constrained by validated metadata.
- Archive uploads are rejected outright in P0, before extraction. Member validation rejects absolute paths, parent traversal, symlinks, and device files for future bundle support.
- Logs default to metadata only; raw dataset rows, prompts, tool data, and reasoning summaries are excluded unless explicitly sanitized.
- Anonymous demo sessions are rate-limited and quota-bound.

## 13. Failure behavior

- A failed OpenAI call does not erase completed deterministic work.
- A probe timeout yields `inconclusive` with partial evidence.
- An unsupported artifact yields a lower reproduction tier, not a fabricated result.
- SSE loss triggers event replay or polling.
- Duplicate SQS delivery is a no-op after the matching checkpoint.
- A correction failure preserves the original and reproduced metrics and explains why corrected performance is unavailable.

## 14. Testing and evaluation

### Software tests

- Unit tests for adapters, parsers, probes, finding policy, state transitions, and sanitization.
- Parametrized tests for archive/path validation and idempotency invariants.
- Contract tests for API envelopes, events, and structured model outputs.
- Integration tests for S3/DynamoDB/SQS behavior using local substitutes or an isolated AWS environment.
- Playwright tests for benchmark intake, follow-up pause/resume, fixture trace, verdict/report, refresh recovery, accessibility, and responsive layouts.

### Audit-quality benchmarks

- Synthetic micro-datasets with one planted mechanism each.
- Multi-leak synthetic cases and a fully clean control.
- Public repository/notebook/model cases with pinned artifacts and predeclared expected findings.
- A licensed UCI COVID-19 surveillance clean control with explicit non-clinical claim boundaries.

Quality reporting includes confirmed-finding precision/recall, false confirmations on clean controls, reproduction error, corrected-metric error, question usefulness, latency, token usage, and cost. A benchmark failure cannot be hidden by changing the expected answer after the run.
