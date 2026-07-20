# Product Requirements Document — PolygraphML

**Version:** 1.1 · **Owner:** David · **Date:** July 18, 2026 · **Status:** Approved foundation

## 1. Product statement

PolygraphML is the evidence-backed lie detector for machine learning systems. A user supplies a trained model, its evaluation dataset, and preferably the notebook or repository that produced it. PolygraphML reconstructs the claimed evaluation, asks scenario questions, reproduces the result, tests leakage and evaluation hypotheses, applies corrections, and explains the difference between reported, reproduced, and corrected performance.

## 2. Product principles

1. **Audit the system, not an isolated dataset.** Model, data, code, split logic, preprocessing, and intended use are evaluated together.
2. **Scenario before verdict.** Whether a feature leaks depends on when and why the prediction is made.
3. **Evidence before accusation.** Semantic suspicion triggers a probe; it does not establish a finding.
4. **The model reasons; code computes.** Numerical results come only from deterministic or explicitly versioned compute steps.
5. **Transparency means inspectability.** Show assumptions, hypotheses, probes, evidence, corrections, and provenance—not raw private chain-of-thought.
6. **One excellent agent first.** A single GPT-5.6 audit agent owns the investigation and may pause for user clarification.
7. **Safe by default.** Uploaded executable artifacts are never loaded in the API process.
8. **Start narrow, design open.** Initial adapters and benchmarks are not permanent product limits.

## 3. Personas

**Priya, ML engineer.** She inherited a churn model reporting AUC 0.97. She has the repository, notebook, model artifact, and evaluation data, but the production result is worse. She needs the claim reproduced and the defect demonstrated.

**Marcus, reviewer or consultant.** He signs off client models and needs a repeatable audit trail that records assumptions, code locations, evidence, and corrections.

**The hackathon judge.** They need to understand the input, see GPT-5.6 make a meaningful semantic contribution, witness deterministic proof, and grasp the product impact in under three minutes.

## 4. Supported submission paths

### 4.1 GitHub repository

The preferred path for the demo is a public GitHub URL plus branch, tag, or commit. The user maps—or lets PolygraphML infer—the notebook/pipeline, dataset location, model artifact, target, and reported metric. The imported commit SHA is recorded. Private-repository OAuth is post-hackathon.

### 4.2 Artifact bundle

The user may upload:

- one dataset (`.csv` or `.parquet`);
- one model artifact (`.skops` for complete P0 reproduction; XGBoost `.json`/`.ubj` and ONNX are accepted only as visibly limited evidence);
- an optional but strongly preferred `.ipynb` notebook or Python pipeline;
- an optional `polygraphml.yaml` manifest mapping files and declaring the scenario.

If the notebook deterministically trains and evaluates the model, a separate model artifact may be omitted. Dataset-only input can receive a labeled **preflight**, not a complete model audit.

### 4.3 Format policy

- JSON is accepted as an XGBoost model only after format validation; arbitrary JSON is metadata, not an executable model.
- `.skops` is the preferred initial scikit-learn interchange format.
- ONNX inference/evaluation is P1 and will require feature ordering and preprocessing metadata; P0 labels the artifact limited.
- Remote pickle, joblib, and cloudpickle uploads are rejected.
- New framework support is added through versioned artifact adapters.

## 5. Core user journey

1. Select **GitHub repository**, **Upload bundle**, or **Try a benchmark**.
2. Review the detected artifacts and fix any ambiguous mapping.
3. Describe the prediction scenario: target, entity, decision point, prediction horizon, split unit, and intended metric.
4. Start the audit. The API creates a durable SQS job and returns immediately.
5. Watch the Decision Trace stream hypotheses, probes, evidence, and corrections.
6. Answer a focused follow-up question if the agent encounters a material ambiguity.
7. Review reported vs. reproduced vs. corrected performance and finding status.
8. Expand any finding to see evidence, source locations, what would change the conclusion, and how to rerun it.
9. Download JSON/Markdown results or generate a stakeholder report.

The screen-level behavior is defined in [PRODUCT_FLOW.md](PRODUCT_FLOW.md).

## 6. Functional requirements

### FR-1 — Submission intake

Create a project from a public GitHub repository or uploaded artifact bundle. Validate types, sizes, checksums, archive paths, and required mappings before an audit can start.

### FR-2 — Artifact reconstruction

Inspect the notebook/repository to identify data loading, preprocessing, split construction, training, evaluation, model serialization, target, reported metric, and relevant source locations. Present inferred mappings for confirmation when confidence is low.

### FR-3 — Scenario contract

Capture target semantics, row/entity meaning, decision time, prediction horizon, feature availability, split unit, and evaluation goal. The agent must ask a concise follow-up when a missing answer could change a finding.

### FR-4 — Reproduction

Run the submitted or reconstructed evaluation in an isolated worker with pinned inputs, seed capture, time/resource limits, and a persisted execution log. Report whether the claimed metric was reproduced within a declared tolerance.

### FR-5 — Semantic audit

Use `gpt-5.6-sol` to propose structured, falsifiable hypotheses about post-outcome features, target proxies, entity contamination, temporal leakage, preprocessing leakage, evaluation mismatch, and suspicious pipeline code. Each hypothesis includes assumptions, rationale summary, requested probe, and falsification condition.

### FR-6 — Deterministic probes

The initial tool suite includes:

- feature availability and post-outcome checks;
- single-feature predictive power;
- exact and near-duplicate contamination;
- group/entity overlap across splits;
- temporal ordering and future-window checks;
- target-proxy association;
- preprocessing-fit-before-split inspection;
- metric and split reconstruction;
- feature ablation and corrected reevaluation.

Probe availability depends on supplied artifacts. Unsupported probes are reported explicitly rather than silently skipped.

### FR-7 — Correction and measured impact

For a supported confirmed defect, construct a corrected evaluation: remove or time-shift unavailable features, repair split boundaries, move preprocessing inside the training fold, or otherwise apply the smallest justified change. Produce reported, reproduced, and corrected metrics with uncertainty/tolerance where applicable.

### FR-8 — Finding lifecycle

A finding can be `needs_context`, `suspected`, `tested`, `confirmed`, `cleared`, or `inconclusive`. `confirmed` requires both mechanism evidence and measured evaluation impact; performance loss from feature ablation alone is not sufficient to prove leakage.

### FR-9 — Decision Trace

Stream and persist sanitized events for assumptions, user answers, hypotheses, tool calls, evidence, corrections, model-generated reasoning summaries, status transitions, warnings, retries, and failures. Every event has an ID, timestamp, actor, and provenance references. Raw hidden reasoning is neither requested nor presented.

### FR-10 — Verdict and reports

Render a polished technical verdict and generate a Markdown stakeholder report. Every reported number is copied from compute-layer objects. Exports include JSON and Markdown; PDF and email are stretch features.

### FR-11 — Benchmark mode

Offer curated synthetic and public benchmark submissions with declared expected findings. Benchmark results are stored separately from user projects and are reproducible from pinned versions.

### FR-12 — Resumability

An audit continues after browser disconnect. The UI can resume using the last event ID or poll the audit state. Duplicate queue delivery must not duplicate an audit or correction.

## 7. Non-functional requirements

### Experience

- React UI is responsive, accessible, visually polished, and understandable without onboarding.
- The live experience never degrades to an unexplained spinner.
- Findings distinguish fact, assumption, inference, and unresolved question.

### Reliability

- API endpoints are idempotent where applicable.
- SQS retries are bounded and exhausted jobs enter a dead-letter queue.
- Partial results remain renderable after a probe or model-call failure.
- The primary demo audit meets the latency budget defined during benchmark calibration; the recorded fallback is deterministic.

### Security and privacy

- OpenAI credentials remain in AWS Secrets Manager and server memory only.
- SQS messages contain audit IDs and S3 references, not artifact bytes, prompts, or secrets.
- Uploaded code executes only in isolated workers with least-privilege IAM, resource limits, restricted egress, and no OpenAI key.
- Artifact retention is explicit and time-bounded.
- Logs and traces redact sensitive inputs by default.

### Quality

- Structured model outputs are schema-validated.
- Metric fields accept only compute-layer provenance.
- Artifact hashes, source commit, package lock, seed, and evaluator version are recorded.
- The system supports a no-key fixture mode for UI and deterministic-engine development.

## 8. MVP acceptance criteria

The hackathon MVP is accepted when all of the following are true:

- a public GitHub benchmark or equivalent upload bundle containing model, data, and notebook completes end to end;
- the original metric is reproduced or the reproduction discrepancy is explicitly diagnosed;
- at least one scenario-dependent issue causes a real follow-up question and resume;
- at least one confirmed leakage/evaluation defect produces a corrected metric;
- each conclusion is traceable from hypothesis to probe to evidence to correction;
- a clean benchmark ends with zero false confirmed findings;
- synthetic planted-leak tests and a curated public benchmark pass their declared expectations;
- browser refresh during an audit does not lose the job or its events;
- the deployed Vercel/AWS demo works without exposing the OpenAI key;
- the critical Playwright path and backend test suite are green.

## 9. Explicit non-goals for the hackathon

The MVP does not promise arbitrary repository execution, private GitHub access, every serialization format, causal proof, production-performance guarantees, clinical validation, multi-agent debate, fairness/drift monitoring, or support for deep-learning modalities. These are roadmap candidates, not hidden expectations.
