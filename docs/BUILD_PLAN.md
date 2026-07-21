# Hackathon Build Plan — PolygraphML

**Submission target:** OpenAI Build Week 2026 · **Detailed DoD:** [IMPLEMENTATION_PHASES.md](IMPLEMENTATION_PHASES.md)

This is the deadline-oriented critical path. It does not replace the phase gates. The demo path must be real, reproducible, and polished before secondary adapters or audit families are added.

## v0.2 final critical path — current

1. Freeze and commit the root manifest, flagship artifacts, expectations, and prohibited claims.
2. Run the public-GitHub import at that exact 40-character SHA.
3. Run the exactly three authorized live evaluations once; preserve failures without expanding or retuning the sweep.
4. Pass clean-checkout CI plus GPT-5.6 Terra review into `dev`, then release review into `main`.
5. Tag `v0.2.0`; deploy API/worker image digests and Vercel from the same SHA; verify `/version`, TLS, CORS, SQS resume/DLQ, repair download, deletion, and secret history.
6. Rotate the OpenAI key, update Secrets Manager and local ignored configuration without exposing it, redeploy the worker, and repeat the relevant smoke checks.
7. Record the 90-second live proof and clearly labeled fixture fallback; verify metadata and submission URLs.

Do not implement the conditional Codex CLI/skill until all seven steps—including both recordings—are complete.

## Day 1 — One trustworthy vertical slice

Build the smallest complete evidence bundle first: one CSV/Parquet dataset, one safe model artifact, one notebook, and one declared scenario. Use a curated benchmark repository so input, expected issue, and corrected result are pinned before implementation.

Order of work:

1. Scaffold React/TypeScript, FastAPI, shared contracts, tests, and fixture mode.
2. Implement artifact inventory and the primary safe adapter path (`.skops` + tabular data + `.ipynb`).
3. Parse the notebook sufficiently to locate target, split, metric, claimed score, and relevant source cells.
4. Implement reported/reproduced/corrected metric objects and one corrected evaluation.
5. Add synthetic ground-truth fixtures before broadening the engine.
6. Capture the active Codex session identifier and record only work that actually exists.

**Day-1 exit:** a backend test or CLI fixture returns all three metric states for the pinned benchmark with provenance and no LLM-generated numbers.

## Day 2 — Agent, durable execution, and product experience

1. Integrate `gpt-5.6-sol` using the OpenAI Agents SDK and typed tools.
2. Implement structured hypotheses, falsification conditions, one material follow-up question, and answer/resume.
3. Implement the initial high-value probes: availability/post-outcome, split/group contamination, preprocessing order, and ablation/corrected evaluation.
4. Persist sanitized `AuditEvent` records and stream the Decision Trace.
5. Add S3/DynamoDB/SQS integration with idempotency, retry, and a DLQ; retain fixture substitutes for local tests.
6. Build the complete React flow: source, mapping, scenario, queue, trace, correction comparison, verdict, and report.

**Day-2 exit:** the browser completes the benchmark audit, survives refresh, pauses for a question, resumes, and lands on a traceable verdict.

## Day 3 — Cloud deployment, evaluation, polish, and submission

1. Deploy the backend to AWS and the frontend to Vercel; configure CORS, Secrets Manager, quotas, and retention.
2. Run the synthetic leak suite, clean control, and curated public benchmark from pinned artifacts.
3. Fix every false confirmed finding and every demo-path reliability issue before adding features.
4. Complete visual polish, accessibility, loading/error states, and 1080p recording checks.
5. Run cold-start, refresh/replay, duplicate-message, missing-key, and partial-failure drills.
6. Record the demo, update the README and Codex log truthfully, and submit with time reserved for upload failures.

**Day-3 exit:** deployed URL, green critical tests, saved benchmark results, final video, complete submission metadata, and no secrets in Git history.

## Non-negotiable demo scope

- model + dataset + notebook/repository evidence;
- scenario-aware follow-up question;
- GPT-5.6 Sol as the central semantic investigator;
- deterministic reported/reproduced/corrected metrics;
- at least one confirmed issue and one cleared check;
- replayable Decision Trace;
- SQS-backed durable job;
- polished React/Vercel experience and AWS backend;
- synthetic clean control plus one public benchmark.

## Cut lines, in order

1. PDF and email export.
2. ONNX support.
3. Additional model adapters beyond the primary `.skops` path.
4. Private GitHub access.
5. Arbitrary notebook execution and dependency installation.
6. Multiple public benchmark cases beyond the one pinned demo case.
7. Non-binary-classification tasks.

Do not cut the Decision Trace, scenario question, corrected metric, clean control, safe artifact policy, or deployed end-to-end path. If GitHub import threatens the core path, keep a working upload/benchmark path and show repository import as clearly labeled partial functionality rather than faking it.

## Standing engineering rules

- Any demo-path defect outranks a new feature.
- No implementation claim enters README or CODEX_USAGE without a corresponding file/test/commit.
- No raw API key, presigned URL, dataset row, or sensitive prompt content enters logs or screenshots.
- Expected benchmark findings are declared before the system runs.
- Freeze benchmark versions and demo data once the critical flow is green.
- Maintain a deterministic fixture-event run for frontend development and recording contingency; never present it as a live audit.
