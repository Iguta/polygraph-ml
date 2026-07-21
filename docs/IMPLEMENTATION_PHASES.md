# Implementation Phases and Definition of Done — PolygraphML

**Version:** 1.2 · **Owner:** David · **Date:** July 21, 2026

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
- [x] A strict root `.polygraphml.yml` path/hash/mapping/scenario/provenance contract is preferred and fetches only declared artifacts.
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
- [x] Approved `.skops` model operations run in a sanitized, resource-bounded child process and are explicitly labeled non-sandboxed.

## Phase 4 — GPT-5.6 audit agent and human loop (P0)

**Outcome:** GPT-5.6 adds scenario-aware semantic investigation through typed, auditable operations.

### Definition of Done

- [x] OpenAI Agents SDK is pinned and configured explicitly with `gpt-5.6-sol` and the Responses API path.
- [x] Local live mode reads `OPENAI_API_KEY`; production design reads Secrets Manager; neither path logs the value.
- [x] Structured hypotheses include assumptions, rationale summary, probe request, and falsification condition.
- [x] The typed planner accepts one to three hypotheses across post-outcome, target-proxy, and metric-contract mechanisms with compatibility validation.
- [x] Every agent tool has a strict input/output schema and bounded execution behavior.
- [x] Agent cannot directly set evidence metrics or promote findings outside the finding-policy tool.
- [x] At least one benchmark triggers a material, concise follow-up question.
- [x] Answer persistence and resume reevaluate the affected hypothesis.
- [x] Reasoning summaries, if enabled, are labeled and stored separately from evidence.
- [x] Schema failure retries are bounded and deterministic analysis remains available after degradation.
- [x] The v0.2 repaired three-case live gate proves `post_outcome` and `target_proxy`, the flagship question, and hard-negative clearance with all three cases live and no degradation (`benchmark-results/live-evaluation-rerun.json`).

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
- [x] Playwright forces three SSE failures, observes polling fallback, verifies clean clearance and measured flagship correction, and downloads a valid repair archive.
- [x] No fixture data, illustrative number, or live state is mislabeled.

## Phase 7 — Benchmark evaluation and release gate (P0)

**Outcome:** the product is measured against known failures and clean controls before claims are made.

### Definition of Done

- [x] Benchmark registry schema includes source, license, hashes, scenario, model, notebook, expectations, tolerance, and prohibited claims.
- [x] Single-mechanism synthetic tests cover each shipped finding type.
- [x] At least one multi-mechanism synthetic case passes.
- [x] At least one fully clean control has zero confirmed findings.
- [x] One public model + dataset + notebook/repository benchmark completes end to end.
- [x] The new v0.2 expectations and prohibited claims were committed at `16dd4c659f4f7f36507d40ff60fbc9280cb82cc5` before `make eval-live`.
- [x] Raw case/pair counts, Wilson intervals, precision/recall, false confirmations, question usefulness, schema failures, degradation, reproduction/correction error, latency, token usage, and cost are reported.
- [x] Public benchmark license and provenance are reviewable from the UI or repository.
- [x] COVID-19 case is included only if reproducibility and licensing gates pass; otherwise it remains explicitly roadmap.
- [x] Every metric in the demo script is replaced with captured benchmark output.
- [x] The seven-case fixture gate has six exact expected pairs, zero false confirmations/negatives, and two clean controls with zero false confirmations.
- [x] The root-manifest flagship imported through the public GitHub API at reviewed candidate `4925f8a4ba28fb06f96277bdb4b1ccc002f969b6`, verified five hashes, completed 27 events, and reproduced/corrected the declared metrics.

## Phase 8 — Deployment and submission readiness (P0)

**Outcome:** the judged experience is deployed, secure enough for public demo traffic, and rehearsed.

### Definition of Done

- [ ] The v0.2 React production build is deployed to Vercel from the release SHA. The prior vertical slice remains deployed but does not satisfy this candidate gate.
- [ ] The v0.2 FastAPI and worker images are deployed to AWS from pinned container digests and the same release SHA.
- [x] TLS, CORS, health checks, quotas, request limits, and artifact retention are configured.
- [x] OpenAI key is stored in Secrets Manager and removed from any ad hoc deployment configuration.
- [x] Repository and Git history pass secret scanning.
- [x] Cold start, live audit, refresh/replay, question/resume, partial failure, and DLQ drills are recorded (`benchmark-results/cold-start-smoke.json` and `benchmark-results/resilience-drill.json` are metadata-only evidence).
- [x] Critical v0.2 CI, backend, benchmark, and Playwright suites are green from a clean checkout on PR #3; backend, frontend, infrastructure, secrets, and GPT-5.6 Terra pass at `13a88e5` before the live evidence commit.
- [ ] README instructions and public `/version` metadata match the deployed v0.2 behavior and exact SHA.
- [x] CODEX_USAGE contains real session IDs, commits, tests, and debugging examples.
- [ ] Demo video stays under the limit and exposes no secrets/account details.
- [ ] Submission metadata, public repository, video URL, and fallback recording are verified before deadline.

## Verification snapshot — July 21, 2026

This table distinguishes the reviewed v0.2 candidate from historical evidence for the already deployed earlier slice.

| Gate | Result | Scope |
|---|---|---|
| Backend suite | Passed | 94 tests and 80.95% branch-aware coverage locally; the same backend gate passes from a clean checkout on PR #3. |
| `make test-e2e` | Passed | Six Playwright tests: forced SSE failure/polling fallback, refresh/replay, provenance-gated live label, flagship correction, executive/technical reports, repair download, clean clearance, axe checks, and mobile/laptop/1080p layout. |
| `make benchmarks` | Passed | Seven fixture cases, six exact expected pairs, zero false confirmations/negatives, two clean controls, schema v2 raw counts and uncertainty. |
| `make public-github-gate` | Passed | Immutable reviewed candidate `4925f8a4ba28fb06f96277bdb4b1ccc002f969b6`, five verified artifacts, 27 events, expected finding and three metrics. |
| First authorized `make eval-live` | Failed honestly | Three cases completed once: flagship hypothesis/question succeeded but answer parsing left it inconclusive; semantic proxy used the wrong mechanism; hard negative degraded. Repair is implemented; another three-call run requires explicit approval. |
| Approved repaired `make eval-live` | Passed | Exactly three cases, all live: flagship `post_outcome:duration` confirmed, `target_proxy:engagement_band` confirmed, and `post_outcome:previous_call_duration` cleared with zero false confirmation; 10,774 tokens and 65,408 ms aggregate agent latency. |
| Terraform init/validate | Passed | AWS provider configuration, exact build-SHA input, repair-download permission, and current topology validate locally. |
| Production npm dependency audit | Passed | Zero known production dependency vulnerabilities; dev-tool advisories are reviewed separately. |
| Prior deployed smoke/resilience evidence | Historical pass | `deployed-smoke.json`, `cold-start-smoke.json`, `resilience-drill.json`, and `queue-timing-live.json` prove the earlier deployed slice, not the v0.2 candidate. |

### Current readiness

- **Locally implemented:** typed multi-mechanism agent boundary, strict manifest/GitHub import, bounded compute, flagship/target-proxy/hard-negative cases, reports, deterministic repair, generated contracts, SSE fallback/replay, and truthful provenance UI.
- **Verified:** complete backend/static/frontend checks, full fixture benchmark, immutable public-GitHub gate, Terraform validation, full Playwright path, and clean-checkout CI/Terra review.
- **Still open for v0.2:** review the new live evidence in PR #3, deploy one release SHA/digest, rerun public smoke/resilience/deletion checks, rotate the key, and record both demos.
- **Conditional bonus:** the Codex CLI/skill is intentionally deferred until every P0 gate and both recordings exist.

## Open-gate record — July 21, 2026

| Owner | Open gate | Why it remains open | Required evidence |
|---|---|---|---|
| Codex + David | v0.2 deployment | Current public URLs serve the earlier slice | Same release SHA in Vercel badge and backend `/version`, pinned ECR digests, public smoke evidence |
| David | Credential rotation | Must occur immediately before the final deployment per the approved plan | Rotated local/Secrets Manager key without exposing its value, then worker redeployment and scans |
| David + Codex | Recordings/submission | No final v0.2 live or labeled fixture recording exists yet | Verified video files/URLs, duration, metadata, and no secret/account exposure |

## Next release actions

1. Let PR #3 clean-checkout CI and GPT-5.6 Terra review the exact live-evidence-bearing candidate.
2. Merge through `dev` to `main`, tag `v0.2.0`, deploy one SHA/digest, rotate the key, and repeat public smoke/security checks.
3. Record and verify the live demo, labeled fixture fallback, and submission metadata.

## P1 — Immediate post-core improvements

- [ ] XGBoost adapter parity if cut from P0.
- [ ] Limited ONNX equivalence checks.
- [ ] More public benchmark cases.
- [x] Technical/executive Markdown report variants and deterministic repair archive.
- [ ] PDF export.
- [ ] Private GitHub authentication.
- [ ] Separate no-secret sandbox executor for approved notebook execution.

## P2 — Roadmap implementation

P2 work follows [ROADMAP.md](ROADMAP.md) and requires its own ADRs, threat model, benchmarks, and DoD. It must not be pulled into the hackathon build merely because an extension point exists.
