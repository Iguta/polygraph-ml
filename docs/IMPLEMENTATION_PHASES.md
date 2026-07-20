# Implementation Phases and Definition of Done — PolygraphML

**Version:** 1.0 · **Owner:** David · **Date:** July 18, 2026

## How to use this plan

Phases are ordered by dependency, not by team specialization. A phase is complete only when every required box is checked or an explicit exception is recorded with owner, reason, risk, and follow-up date. Screenshots and “works on my machine” do not replace automated verification.

Priority labels:

- **P0:** required for the hackathon demo and submission.
- **P1:** implement only after every P0 dependency is stable.
- **P2:** roadmap; do not jeopardize P0.

## Phase 0 — Foundation and safety contract (P0)

**Outcome:** the repository has one coherent product and technical contract before code branches multiply.

### Definition of Done

- [x] README, BRD, PRD, TDD, architecture, API, product flow, roadmap, demo, and build-plan terminology is cross-checked.
- [x] The canonical finding statuses and reported/reproduced/corrected metric meanings are identical across code-facing documents.
- [x] An ADR records the single-agent decision and criteria for reconsidering it.
- [x] An ADR records safe model formats and explicit pickle/joblib/cloudpickle rejection.
- [x] An ADR records Vercel + AWS + SQS and the key trust boundaries.
- [x] `.env` is ignored; `.env.example` contains names only; secret scanning is configured.
- [x] The OpenAI key is non-empty under the exact local variable name `OPENAI_API_KEY` without exposing its value (verified by `make deployment-preflight` on July 19, 2026).
- [x] No document claims implementation or test completion without evidence.

## Phase 1 — Application skeleton and fixture vertical slice (P0)

**Outcome:** frontend and backend share contracts and can demonstrate the full state progression without live APIs.

### Definition of Done

- [x] React + TypeScript app, FastAPI app, worker package, and shared schema package are scaffolded.
- [x] One documented command starts the local frontend, API, and worker substitutes.
- [x] Formatting, linting, type checking, backend tests, and frontend tests run in CI.
- [x] API health/readiness endpoints and frontend error boundary exist.
- [x] Generated API types or contract tests prevent schema drift.
- [x] Fixture mode replays a complete audit event stream with no OpenAI key.
- [x] Fixture mode is visibly labeled and cannot be mistaken for a live audit.
- [x] A Playwright smoke test reaches the fixture verdict from the landing page.

## Phase 2 — Project intake and evidence mapping (P0)

**Outcome:** a user can submit a pinned repository or safe bundle and understand what PolygraphML found.

### Definition of Done

- [x] Project/session endpoints and quota checks conform to the API contract.
- [x] Presigned S3 upload flow verifies size, checksum, type, and project scope.
- [x] Public GitHub import resolves the supplied ref to an immutable commit SHA.
- [x] Repository/archive validation rejects traversal, symlinks, device files, and expansion bombs.
- [x] CSV and Parquet dataset adapters emit the canonical profile.
- [x] `.skops` adapter accepts an allowlisted test model and rejects an unsupported type safely.
- [x] XGBoost JSON/UBJ is either tested or explicitly marked P1 in the UI.
- [x] Remote pickle, joblib, cloudpickle, and arbitrary model JSON are rejected before loading.
- [x] Notebook parser locates representative split, preprocessing, training, metric, and printed-claim cells.
- [x] Artifact-map UI lets the user correct ambiguous mappings.
- [x] Dataset-only input is labeled preflight and cannot start a complete audit.

Archive policy: archive formats are rejected at the extension allowlist, so an archive bomb is never expanded. Member-path validation remains unit-tested for future bundle support.

## Phase 3 — Scenario, reproduction, and deterministic evidence (P0)

**Outcome:** PolygraphML can reconstruct the claim and compute trustworthy comparison objects without an LLM.

### Definition of Done

- [x] Scenario schema captures target, entity, decision time, horizon, split unit, metric, and notes.
- [x] Reproduction tiers are implemented and visible in results.
- [x] Reported metric extraction includes an artifact/source reference.
- [x] Primary benchmark metric is reproduced within a predeclared tolerance or the mismatch is diagnosed.
- [x] Split indices/hashes, seed, feature order, versions, and artifact hashes are recorded.
- [x] Availability/post-outcome, duplication/group overlap, preprocessing-order, and ablation/correction tools have unit tests.
- [x] Corrected evaluation applies the smallest documented repair and produces compute-owned metrics.
- [x] Finding-policy tests prove that ablation delta alone cannot confirm leakage.
- [x] Unsupported probes become visible limitations, not silent omissions.
- [x] No quantitative result field accepts free-form model output.

## Phase 4 — GPT-5.6 audit agent and human loop (P0)

**Outcome:** GPT-5.6 adds scenario-aware semantic investigation through typed, auditable operations.

### Definition of Done

- [x] OpenAI Agents SDK is pinned and configured explicitly with `gpt-5.6-sol` and the Responses API path.
- [x] Local live mode reads `OPENAI_API_KEY`; production design reads Secrets Manager; neither path logs the value.
- [x] Structured hypotheses include assumptions, rationale summary, probe request, and falsification condition.
- [x] Every agent tool has a strict input/output schema and bounded execution behavior.
- [x] Agent cannot directly set evidence metrics or promote findings outside the finding-policy tool.
- [x] At least one benchmark triggers a material, concise follow-up question.
- [x] Answer persistence and resume reevaluate the affected hypothesis.
- [x] Reasoning summaries, if enabled, are labeled and stored separately from evidence.
- [x] Schema failure retries are bounded and deterministic analysis remains available after degradation.
- [x] Sanitized developer trace proves the real agent/tool loop without exposing secrets or raw data (`benchmark-results/live-trace.json`, 23 events, `gpt-5.6-sol`).

## Phase 5 — Durable AWS execution and event replay (P0)

**Outcome:** audits continue independently of the browser and recover safely from normal distributed-system failures.

### Definition of Done

- [x] Infrastructure as code provisions S3, DynamoDB, SQS, DLQ, Secrets Manager reference, ECS services/tasks, IAM, and CloudWatch alarms.
- [x] API persists `queued` before sending the SQS message.
- [x] Messages contain identifiers/references only and pass a secret/payload contract test.
- [x] Worker uses a conditional lease and idempotent checkpoints.
- [x] Visibility timeout/heartbeat settings are based on 20 deployed live audit durations (`benchmark-results/queue-timing-live.json`: P95 32.666s, recommendation 161s, configured visibility 300s and heartbeat 60s).
- [x] A duplicate message does not duplicate events, corrections, or reports.
- [x] A user-question pause releases the job; answering creates one resume job.
- [x] Exhausted retryable failure reaches the DLQ and produces an operator-visible alarm.
- [x] SSE replays from the last event ID; JSON polling provides a tested fallback.
- [x] Refreshing or closing the browser does not stop or lose the audit.
- [x] OpenAI credentials are available only to the coordinator role.
- [x] Retention/deletion behavior is documented and tested against a disposable project.

## Phase 6 — Polished React product (P0)

**Outcome:** the complete workflow feels deliberate, intuitive, and trustworthy under demo conditions.

### Definition of Done

- [x] A small design system defines color, type, spacing, motion, status, focus, and responsive behavior.
- [x] All seven states in PRODUCT_FLOW are implemented with empty/loading/error/partial variants.
- [x] Artifact support and limitations are understandable before audit start.
- [x] Scenario questions explain why the answer matters.
- [x] Decision Trace differentiates assumptions, model summaries, tools, evidence, and conclusions.
- [x] Source references and “What would change this?” are accessible from each finding.
- [x] Reported/reproduced/corrected metrics include protocol and provenance details.
- [x] Correction animation respects reduced-motion settings and never obscures labels.
- [x] Keyboard navigation, focus order, contrast, and screen-reader names pass the chosen accessibility checks.
- [x] Layout is verified at mobile, laptop, and 1080p recording sizes.
- [x] Playwright covers upload/benchmark intake, mapping, question/resume, refresh/replay, verdict, and report.
- [x] No fixture data, illustrative number, or live state is mislabeled.

## Phase 7 — Benchmark evaluation and release gate (P0)

**Outcome:** the product is measured against known failures and clean controls before claims are made.

### Definition of Done

- [x] Benchmark registry schema includes source, license, hashes, scenario, model, notebook, expectations, tolerance, and prohibited claims.
- [x] Single-mechanism synthetic tests cover each shipped finding type.
- [x] At least one multi-mechanism synthetic case passes.
- [x] At least one fully clean control has zero confirmed findings.
- [x] One public model + dataset + notebook/repository benchmark completes end to end.
- [ ] Expected findings are committed before live benchmark execution.
- [x] Precision/recall, false confirmations, reproduction error, corrected-metric error, latency, token usage, and estimated cost are reported.
- [x] Public benchmark license and provenance are reviewable from the UI or repository.
- [x] COVID-19 case is included only if reproducibility and licensing gates pass; otherwise it remains explicitly roadmap.
- [x] Every metric in the demo script is replaced with captured benchmark output.

## Phase 8 — Deployment and submission readiness (P0)

**Outcome:** the judged experience is deployed, secure enough for public demo traffic, and rehearsed.

### Definition of Done

- [x] React production build is deployed to Vercel with the intended domain.
- [x] FastAPI and worker images are deployed to AWS from pinned container digests.
- [x] TLS, CORS, health checks, quotas, request limits, and artifact retention are configured.
- [x] OpenAI key is stored in Secrets Manager and removed from any ad hoc deployment configuration.
- [x] Repository and Git history pass secret scanning.
- [x] Cold start, live audit, refresh/replay, question/resume, partial failure, and DLQ drills are recorded (`benchmark-results/cold-start-smoke.json` and `benchmark-results/resilience-drill.json` are metadata-only evidence).
- [ ] Critical CI, backend, benchmark, and Playwright suites are green from a clean checkout.
- [x] README instructions match the implemented commands and deployed behavior.
- [ ] CODEX_USAGE contains real session IDs, commits, tests, and debugging examples.
- [ ] Demo video stays under the limit and exposes no secrets/account details.
- [ ] Submission metadata, public repository, video URL, and fallback recording are verified before deadline.

## Verification snapshot — July 20, 2026

The following checks were run against the current working tree:

| Command | Result | What it proves |
|---|---|---|
| `make check` | Passed | Ruff format/lint, mypy, 45 backend tests at 81.27% coverage, 5 frontend tests, OpenAPI export, and whitespace checks pass. |
| `make test-e2e` | Passed | Four Playwright scenarios pass: fixture verdict, refresh/resume, mobile, laptop, and 1080p recording layout coverage. |
| Throwaway clean-checkout rehearsal | Passed | A temporary Git snapshot/clone completed dependency installation, `make check`, and `make test-e2e`; it validates release reproducibility but does not replace the final reviewed project commit. |
| `make live-smoke` | Passed | Sanitized trace recorded with 23 events and model `gpt-5.6-sol`. |
| `polygraphml-deployed-smoke --api-url … --mode live` | Passed | Public API → SQS → worker audit completed with replay, question/resume, and project deletion; output contains metadata only. |
| Controlled retry/DLQ drill | Passed | A disposable missing-project fault retried three times, ended `failed_partial`/`dead_lettered`, reached the DLQ, and was cleaned (`benchmark-results/resilience-drill.json`). |
| Worker cold-start smoke | Passed | The worker was scaled to zero, fresh-started, and then completed the public live audit flow (`benchmark-results/cold-start-smoke.json`). |
| `polygraphml-queue-calibration --input benchmark-results/deployed-live-timings.json` | Passed | 20 deployed live durations; P95 32.666s, recommendation 161s, configured 300-second visibility and 60-second heartbeat cover the sample. |
| AWS API health | Passed | ALB target healthy; `/healthz` at `api.polygraphml.davidiguta.com` returned HTTP 200. |
| Vercel custom domain | Passed | `polygraphml.davidiguta.com` returned HTTP 200 over HTTPS. |

### Readiness summary

- **P0 checklist:** 85 of 92 items complete (**92%**).
- **Local MVP:** complete and verified through backend, frontend, contract, benchmark, and Playwright gates.
- **Cloud deployment:** ACM is issued; the pinned ECS/ALB/SQS/DynamoDB/S3/WAF stack is applied; API and worker are healthy; the Vercel custom domain is live.
- **Public release:** partially complete. The deployed URLs, live-agent evidence, cold-start, partial-failure, and DLQ recovery evidence work; final Git review and submission packaging remain outstanding.

These results prove the local fixture vertical slice, a real sanitized GPT-5.6 agent trace, deployed AWS/Vercel health surfaces, and the production resilience-drill matrix. The remaining P0 gates are review/commit and submission artifacts, not unverified runtime behavior.

## Open-gate record — July 19, 2026

| Owner | Open gate | Evidence/reason | Risk | Follow-up |
|---|---|---|---|---|
| David | Sanitized live trace | `make live-smoke` captured a metadata-only trace with 23 events and no sensitive payloads | Live semantic path is now demonstrated | Preserve the trace and include it in the reviewed submission evidence |
| David + Codex | Live queue-duration calibration | `queue-timing-live.json` records 20 deployed live durations and confirms the configured 300-second visibility / 60-second heartbeat exceed the 161-second recommendation | Continue to revisit after materially larger workloads | Review the calibration during post-hackathon scaling work |
| David | Benchmark expectation commit | Registry and results are present only in the working tree | Expectations could still change without Git history | Review and commit expectations before any live benchmark run |
| David + Codex | Production resilience drills | DNS, ACM, ECS/ALB, Vercel, a deployed live audit, event replay, question/resume, deletion, controlled partial failure/DLQ handoff, and clean worker cold start are verified (`benchmark-results/resilience-drill.json`, `benchmark-results/cold-start-smoke.json`) | None | Retain metadata-only outputs for submission review |
| David | Submission evidence | The active Codex thread and starting commit are recorded; reviewed implementation commit, public URL, video, and metadata are not yet available | Submission package is incomplete | Record the remaining evidence after review, deployment, and rehearsal |

## Next actions for the owner

Complete these in order; each item is a prerequisite for the next release gate:

1. **Review the release.** Run secret scanning and the full critical test suite from a clean checkout, review the diff, and commit the implementation.
2. **Package the submission.** Record the public URL, demo video, and submission metadata.

## P1 — Immediate post-core improvements

- [ ] XGBoost adapter parity if cut from P0.
- [ ] Limited ONNX equivalence checks.
- [ ] More public benchmark cases.
- [ ] Technical/executive report variants and PDF export.
- [ ] Private GitHub authentication.
- [ ] Separate no-secret sandbox executor for approved notebook execution.

## P2 — Roadmap implementation

P2 work follows [ROADMAP.md](ROADMAP.md) and requires its own ADRs, threat model, benchmarks, and DoD. It must not be pulled into the hackathon build merely because an extension point exists.
