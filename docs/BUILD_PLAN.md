# Build Plan — PolygraphML (3 days)

**Submission deadline:** July 21, 2026, 5:00 PM PT. Everything below serves one goal: the demo path runs flawlessly, twice, on camera.

## Day 1 — Engine end-to-end (ugly is fine)

The day ends with a curl-driven audit completing on the synthetic churn dataset. In order: scaffold the repo with Codex (FastAPI app, React shell, Makefile, uv/npm wiring) and **capture the Codex Session ID immediately via `/feedback`**; write the synthetic dataset generator with all five planted leak types plus the clean control — ground truth exists before the engine does; implement intake + profiling; implement the semantic auditor call with the Finding schema and validation; implement two probes (single-feature power, proxy correlation); implement the ablation prover with logistic regression + XGBoost baselines. Definition of done: `POST /datasets` → `POST /audits` → `GET /audits/{id}` returns proven findings on the planted proxy leak, all from the terminal.

## Day 2 — The product

Morning: remaining probes (contamination, temporal), the SSE event stream, and the verdict composer with templated metrics. Afternoon: the dashboard — intake state, live interrogation view with feature chips and streaming narration, the proof card with the metric-collapse animation, verdict panel, report view. Codex writes the pytest suite against the synthetic datasets (every planted leak caught, clean dataset produces zero Proven findings) and the Playwright smoke test of the demo path. Definition of done: a stranger can run `make dev`, click through upload → interrogate → proof → report on the sample dataset, and the full test suite is green.

## Day 3 — Polish, proof, submission

Morning: visual polish on the five states (this is a judged Design criterion — spacing, typography, the collapse animation timing), latency tuning to keep the audit under 90 seconds, and the stakeholder report quality pass. Midday: record the demo video per [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — multiple takes, pick one, upload to YouTube. Afternoon: README final pass, [CODEX_USAGE.md](CODEX_USAGE.md) with session narrative and ID, Dockerfile verification (`docker compose up` cold-start test), repo hygiene (squash WIP commits on `dev`, merge to `main`), Devpost submission with hours to spare. **Submit by 2:00 PM PT — never race the deadline.**

## Cut lines (execute in this order if behind)

First cut: email delivery (FR-8) — the report on screen carries the demo. Second: pickled-model intake (FR-9) — built-in baselines suffice. Third: temporal probe — three probe types still demonstrate the category; keep the planted temporal leak out of the demo dataset if its probe is cut. Fourth: report audience toggle — ship executive-voice only. **Never cut:** the semantic audit, the ablation proof loop, the clean-feature clearance, the synthetic test suite, or the live narration — these are, respectively, the GPT-5.6 story, the wow moment, the credibility, the technical-effort evidence, and the design signature.

## Standing rules

Commit to `dev` continuously; `main` receives only working states. Any bug on the demo path outranks any feature anywhere. Every Codex session that touches core functionality gets its session noted in CODEX_USAGE.md the same hour. If a live component becomes flaky within six hours of recording, freeze its inputs and demo the frozen path — determinism beats ambition on camera.
