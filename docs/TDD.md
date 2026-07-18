# Technical Design Document — PolygraphML

**Version:** 1.0 · **Owner:** David · **Date:** July 18, 2026 · **Status:** Approved for build

## 1. Overview

PolygraphML is a two-tier application: a Python FastAPI backend hosting the audit engine, and a React single-page dashboard. The audit engine is an agent loop in which GPT-5.6 plans and interprets while deterministic Python code executes probes and retraining. The critical design principle: **the model reasons, the code computes.** Every number shown to the user is computed by Python and injected into GPT-5.6 prompts as ground truth; GPT-5.6 never generates a metric.

## 2. Components

**Intake service.** Parses uploaded CSVs with pandas, infers dtypes, computes per-feature summary statistics (cardinality, missingness, distribution sketch, sample values), and writes a `DatasetProfile`. Rejects files over 50 MB or without a valid target column.

**Semantic auditor (GPT-5.6).** One structured-output call per audit. Input: dataset profile, target description, optional time column, optional user-supplied business context. Output: per-feature `RiskAssessment` (risk level, suspected mechanism, rationale). Model: `gpt-5.6-sol` for this call (deepest reasoning step); cheaper tiers (`terra`/`luna`) for narration and report drafting. Temperature low; schema enforced via structured outputs; one retry on validation failure.

**Probe harness.** Deterministic Python implementations of the four core probes.

| Probe | Method | Signal |
|---|---|---|
| Single-feature power | Per-feature model (decision stump / univariate logistic) AUC vs. target on a held-out split | AUC > threshold (default 0.85) flags target proxy |
| Contamination | Exact and near-duplicate rows (hash + MinHash) across train/test split | Any cross-split duplication flags contamination |
| Temporal ordering | With a time column: feature availability vs. outcome timestamp; correlation of feature with future windows | Feature knowable only post-outcome flags temporal leak |
| Proxy correlation | Normalized mutual information feature↔target | NMI above adaptive threshold flags proxy |

Each probe returns an `Evidence` object; probes run in a worker with a hard timeout.

**Ablation prover.** For each suspect set, trains baseline models (logistic regression and XGBoost, fixed seeds, stratified split) on all features, then retrains excluding the suspects, and records `baseline_metric`, `ablated_metric`, `delta`. Uses small demo-scale data so each retrain is O(seconds). A suspect graduates to **Proven** only if delta exceeds a materiality threshold (default 5 points of AUC/accuracy) — this is what keeps false accusations out.

**Verdict composer (GPT-5.6).** Receives the full computed findings and writes the interrogation narrative and the stakeholder report. All quantitative values are templated in; the model supplies mechanism explanations and business translation only.

**Event stream.** The audit runs as an async task; every state transition (profiling, suspicion raised, probe started/finished, proof running, proof result, verdict) is pushed to the client over SSE, giving the live-narration UX.

## 3. Agent loop

The loop is intentionally simple and inspectable rather than autonomous: `profile → semantic audit → probe suspects → ablate confirmed suspects → compose verdict`. GPT-5.6 makes two kinds of decisions inside the loop: which probes apply to which features (the probe plan), and how to interpret ambiguous probe results (e.g., high single-feature AUC on a plausibly legitimate feature triggers a follow-up ablation rather than an accusation). Implemented with the OpenAI Agents SDK; each step is a typed tool with logged inputs/outputs so the full session is auditable — which doubles as demo material.

## 4. Data model

Core entities (full JSON schemas in [API_CONTRACT.md](API_CONTRACT.md)): `Dataset` (id, profile, target, time_column), `Audit` (id, dataset_id, status, findings[], proofs[], verdict), `Finding` (feature(s), type ∈ {target_proxy, post_outcome, contamination, temporal, identifier}, severity, confidence, rationale, evidence[], status ∈ {suspected, probed, proven, cleared}), `Proof` (features, model, baseline_metric, ablated_metric, delta, verdict). Persistence is a per-session directory of JSON files — no database for the MVP.

## 5. Synthetic evaluation suite

Ground truth is manufactured, not assumed. A generator script produces datasets with planted leaks of each type: a direct target proxy (target + noise), a post-outcome field (populated only for positive class), cross-split duplicates, a temporal bleed (feature computed from a post-outcome window), and an identifier leak — plus one fully clean dataset. The pytest suite asserts every planted leak is detected and proven, and that the clean dataset produces zero Proven findings. This suite is Codex-authored and is the centerpiece of the hackathon's "genuine technical effort" story.

## 6. Key design decisions

Local training over SageMaker: demo latency and self-containment beat cloud credibility theater; SageMaker is documented as roadmap. Baseline-model ablation over user-model introspection: retraining our own baselines makes proofs uniform, fast, and model-agnostic; pickled-model support is a stretch. Structured outputs everywhere: a malformed model response must be impossible to render. Materiality threshold on proofs: detection sensitivity is worthless if the tool cries wolf; the threshold plus the clean-dataset test enforces precision.

## 7. Error handling and failure modes

Probe timeout marks the finding `probed` with partial evidence rather than failing the audit. GPT-5.6 schema-validation failure retries once, then degrades to statistical-only findings with a visible notice. Retrain failure on a suspect surfaces the finding as `suspected` with the error attached. The SSE channel reconnects with resume-from-last-event. The audit as a whole must never hard-fail on a single component: partial verdicts are always renderable.

## 8. Testing strategy

Unit tests cover each probe against hand-constructed micro-datasets; the synthetic suite covers the end-to-end engine; a Playwright smoke test covers upload → interrogate → verdict on the demo dataset. Target for the hackathon: the synthetic suite green plus the Playwright path green constitutes "demo-ready." Codex generates and maintains all three layers, with the session log preserved as evidence.
