# Product Flow — PolygraphML

**Version:** 1.1 · **Experience:** one responsive React workspace with seven progressive states

The product transforms in place so the user retains context. A compact stepper and persistent project header provide orientation without turning the experience into a long configuration wizard.

## State 1 — Choose evidence

The landing view leads with the promise: **“Find out whether your model earned its score.”** Three clear actions are offered:

1. **Audit a GitHub repository** — enter a public repository URL and optional branch/tag/commit.
2. **Upload model evidence** — upload dataset, model artifact, and optional notebook/manifest.
3. **Try a benchmark** — open a curated, fully reproducible example.

Each choice explains what a complete audit requires. Dataset-only uploads are labeled **Dataset preflight**, not presented as full model audits. The primary demo reaches source selection within ten seconds.

## State 2 — Review artifact map

PolygraphML displays the detected evidence as cards:

- dataset and candidate target;
- model format and adapter status;
- notebook/pipeline and likely training/evaluation cells;
- reported metric and source location;
- source commit and artifact checksums.

Ambiguous or missing mappings are visually obvious and editable. Unsupported artifacts remain listed with a reason and a safe next step. A remote pickle is rejected here, before any execution path.

## State 3 — Define the prediction scenario

The user confirms a concise scenario contract:

- What does one row represent?
- What outcome is predicted?
- At what moment must the prediction be available?
- What is the prediction horizon?
- What entity/group must not cross evaluation splits?
- Which metric should determine success?

Known values are prefilled from the notebook or manifest. The purpose is explained in one sentence: **the same feature can be valid or leakage depending on when the prediction is made.** The main action is **Start audit**.

## State 4 — Queued and reconstructing

The API returns immediately after creating the SQS job. The UI shows a durable audit ID and the concrete first steps: importing artifacts, profiling, locating evaluation code, and reproducing the claim. A browser refresh reconnects to the same audit.

This state never uses an unexplained spinner. Every step is either pending, running, complete, needs input, or failed with a recoverable explanation.

## State 5 — Live Decision Trace

The main workspace splits into:

- a feature/source rail showing current statuses;
- a timeline of structured audit events;
- a contextual evidence drawer.

Timeline cards are explicitly typed: **Assumption**, **Hypothesis**, **Probe**, **Observation**, **Correction**, or **Conclusion**. A hypothesis states the concise rationale, what will be tested, and what would disprove it. Probe cards show actual tool inputs and results. Source references open the relevant notebook cell, file, column, or artifact metadata.

The product does not label this view “chain-of-thought.” It shows a sanitized, user-auditable decision trace. Optional OpenAI reasoning summaries may supply concise narration, but are visually distinct from computed evidence.

### Human-in-the-loop pause

When a missing scenario fact could change the conclusion, the trace pauses with one focused question. For example:

> “Is `call_duration` available when the campaign decides whom to call, or only after the call finishes?”

The user answer is recorded as an event, affected hypotheses are reevaluated, and the same SQS-backed audit resumes. The rest of the page remains inspectable while paused.

## State 6 — Correction and comparison

For a confirmed defect, a comparison card shows:

- **Reported** metric from the submitted evidence;
- **Reproduced** metric from PolygraphML’s reconstruction;
- **Corrected** metric after the smallest justified repair.

The animation may dramatize the change, but the labels, evaluation split, confidence/tolerance, and correction must remain visible. Feature ablation alone is shown as impact evidence; it becomes a confirmed leakage finding only when paired with mechanism evidence such as unavailable-at-decision-time or cross-split contamination.

## State 7 — Verdict and report

The final workspace includes:

- a trust summary with reported/reproduced/corrected metrics;
- findings ranked by severity and status;
- assumptions and unresolved questions;
- cleared checks and unsupported checks;
- reproducibility metadata;
- **Download JSON**, **Generate stakeholder report**, and **Run another audit** actions.

Every finding expands into a trace from hypothesis to evidence to correction, including “What would change this conclusion?” A fully clean result is a first-class success state: **“No tested leakage mechanism was confirmed under the stated scenario.”** It never overclaims universal safety.

## Error and edge flows

- A malformed or oversized artifact returns to the mapping state with a specific remediation.
- An unsupported model can still receive repository/notebook analysis, but the UI clearly marks model-level reproduction as unavailable.
- A model-call failure leaves deterministic results visible and offers a bounded retry.
- A probe timeout produces an `inconclusive` result rather than a false clearance or confirmation.
- An SQS retry does not duplicate events or corrections; the UI may display the retry count.
- A disconnected SSE stream falls back to polling and resumes from the last event ID.
- A missing API key disables live semantic analysis with a clear configuration notice; benchmark fixtures and deterministic UI flows remain usable in development.

## Demo mapping

The hackathon video emphasizes State 1–3 briefly, spends most of its time in the live Decision Trace and correction comparison, and lands on the verdict. Each state must be screenshot-worthy, keyboard accessible, and legible at 1080p recording scale.
