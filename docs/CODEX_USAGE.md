# How Codex Is Building PolygraphML

This is an evidence log for the OpenAI Build Week submission. It must describe completed work truthfully. Planned work stays labeled **planned** until the referenced implementation and verification exist.

## Codex session IDs

- Active Codex thread: `019f77f9-27da-7560-b2ea-9b42e521ad49` (captured from the active goal metadata).

## Git references

- Starting documentation commit: `a4291caadc53fe27c7fefbda501f29076d52b227` (`docs: PolygraphML starter documentation suite`).
- Implementation commit: `0d8f00caefb6150ff3d86d30396c478a030612d9` (`feat: ship PolygraphML audit platform`).
- Release-branch CI hardening: `2e3ee05`, `fa11d28`, `f738301`, and `e924c84`.
- Review PR: [#1 — prior `agent/polygraphml-release` release](https://github.com/Iguta/polygraph-ml/pull/1), merged at `22660b7` and present on both `origin/dev` and `origin/main`. The v0.2 candidate is on `agent/hackathon-winning-slice` and has no PR yet.
- v0.2 expectation-bearing implementation commit: `16dd4c659f4f7f36507d40ff60fbc9280cb82cc5` (`feat: ship hackathon-winning evidence slice`), created before any v0.2 live evaluation.

## Current repository state

As of July 21, 2026, the earlier vertical slice is deployed at `polygraphml.davidiguta.com`, but the committed, not-yet-published `v0.2.0` candidate is a materially larger change and must not be confused with that deployment. The candidate adds a typed multi-mechanism agent contract, strict root manifest, full UCI Bank Marketing flagship, bounded child compute, semantic proxy/hard negative, benchmark schema v2, real executive/technical reports, deterministic repair bundles, generated frontend contracts, authenticated SSE/replay/fallback, and exact build provenance. The 82-test backend suite, static checks, frontend unit/build gates, seven-case fixture gate, Terraform validation, two candidate container builds, and six-test Playwright suite pass locally. Public immutable-SHA import, the exactly three live evaluations, clean-checkout CI/Terra review, v0.2 deployment, credential rotation, and both recordings remain open.

## Completed Codex work

### Foundational product review — July 18, 2026

Codex challenged and revised the initial dataset-only concept into a model-system audit. The accepted scope now evaluates the model, dataset, and notebook/repository together; captures the prediction scenario; distinguishes reported, reproduced, and corrected metrics; and defines evidence-backed finding criteria.

### Architecture and contract revision — July 18, 2026

Codex documented:

- React on Vercel and FastAPI/workers on AWS;
- S3, DynamoDB, SQS/DLQ, Secrets Manager, and ECS Fargate responsibilities;
- public GitHub and safe artifact-bundle intake;
- initial `.skops`, XGBoost JSON/UBJ, and limited ONNX format policy;
- rejection of remote pickle-like artifacts;
- one GPT-5.6 Sol audit agent using the OpenAI Agents SDK;
- a user-visible Decision Trace that does not claim to expose raw chain-of-thought;
- phased implementation and Definition-of-Done gates.

### Functional vertical slice — July 18, 2026

Codex implemented FastAPI, a durable worker coordinator, local and AWS repositories/queues/artifact stores, generated OpenAPI contracts, React/TypeScript, and the full fixture audit lifecycle. The browser can select a benchmark, confirm its artifact map and scenario, survive refresh, answer a persisted question, inspect a differentiated Decision Trace, compare metrics, expand falsification conditions, and generate a report.

**Evidence:** `src/polygraphml/`, `frontend/src/`, `packages/contracts/openapi.json`, `tests/test_audit_lifecycle.py`, and `frontend/e2e/fixture-audit.spec.ts`.

### Safe intake and deterministic audit — July 18, 2026

Codex implemented public GitHub commit pinning, direct/local uploads, artifact ownership and quota checks, CSV/Parquet, `.skops`, limited XGBoost/ONNX labeling, static notebook inspection, explicit rejection of pickle-family formats, reproduction, availability/contamination/preprocessing probes, finding policy, correction, and provenance-rich metrics. The API verifies S3 metadata without downloading direct-upload bytes; workers fetch artifacts inside the execution boundary.

**Evidence:** `tests/test_artifact_safety.py`, `tests/test_adapters.py`, `tests/test_api_contract.py`, `tests/test_probes_policy.py`, and `tests/test_aws_adapters.py`.

### Agent and human loop — July 18–21, 2026

Codex pinned the OpenAI and Agents SDKs, configured explicit `gpt-5.6-sol` Responses API execution with high reasoning effort, typed read-only agent tools, one-to-three structured hypotheses, a mechanism/probe compatibility registry, one material question, bounded five-turn execution/fallback, and separate rationale summaries. The coordinator dispatches post-outcome, target-proxy, and metric-contract probes while deterministic split/group/preprocessing probes run automatically. Fixture mode proves persistence/policy without claiming a model call. The earlier live trace proves only the prior post-outcome path; the v0.2 three-case live gate remains open.

**Evidence:** `src/polygraphml/agent/runtime.py`, `src/polygraphml/worker/coordinator.py`, `src/polygraphml/benchmarks/live_evaluate.py`, `tests/test_deterministic_evidence.py`, and `tests/test_live_evaluation.py`.

### Winning v0.2 evidence slice — July 21, 2026

Codex implemented the strict `.polygraphml.yml` schema and manifest-first public GitHub importer; safe `.skops` evaluation/correction in a child process capped at 120 wall seconds, 90 CPU seconds, 2 GiB address space, 64 descriptors, bounded output, single-thread libraries, sanitized environment, and process-group termination; the full licensed 45,211-row UCI Bank Marketing benchmark; a semantic target proxy; a suspicious hard negative; and a seven-case evaluator with raw counts, Wilson intervals, quality/degradation/token/latency fields, and the deterministic/semantic/full ablation comparison.

**Evidence:** `.polygraphml.yml`, `scripts/generate_uci_bank_benchmark.py`, `src/polygraphml/adapters/manifests.py`, `src/polygraphml/engine/bounded_compute.py`, `src/polygraphml/benchmarks/`, `benchmark-results/latest.json`, `tests/test_manifests.py`, `tests/test_github_intake.py`, `tests/test_bounded_compute.py`, and `tests/test_benchmark_evaluation.py`.

### Self-proving product experience — July 21, 2026

Codex replaced interval-only fetching with authenticated fetch-based SSE, `Last-Event-ID`, reconnect backoff, JSON polling fallback, and session refresh replay; made mode/model/build labels derive from stored provenance; regenerated OpenAPI frontend types; separated executive and technical reports; and added idempotent hash-addressed repair archives for unambiguous literal feature lists. Playwright forces stream failure, refreshes the flagship audit, verifies the measured `0.871 → 0.733` comparison, generates both reports, downloads the repair, proves four clean-control clearances with zero confirmations, runs axe, and checks three viewport classes.

**Evidence:** `frontend/src/`, `frontend/e2e/fixture-audit.spec.ts`, `src/polygraphml/services/reporting.py`, `src/polygraphml/services/repairs.py`, `tests/test_repairs.py`, `packages/contracts/openapi.json`, and the passing July 21 Playwright run.

### AWS and Vercel definitions — July 18, 2026

Codex added Docker images and Terraform for S3, DynamoDB, SQS/DLQ, Secrets Manager, ECR, ECS Fargate, IAM, CloudWatch, ALB TLS, and Route 53. Terraform validation and both local container builds pass. The browser's presigned-upload regression test proves that the session bearer token is not sent to S3. The stack is deployed and its public health surfaces are verified.

**Evidence:** `infra/terraform/`, `Dockerfile.api`, `Dockerfile.worker`, `docs/DEPLOYMENT.md`, `tests/test_aws_adapters.py`, and `frontend/src/api.test.ts`.

### Cloud deployment — July 19–20, 2026

Codex verified the `PolygraphMLDeployer` AWS identity and Vercel CLI authentication, created and delegated the Route 53 zone for `polygraphml.davidiguta.com`, validated the ACM certificate for `api.polygraphml.davidiguta.com`, created ECR repositories and the Secrets Manager container with Terraform, stored the OpenAI key in Secrets Manager without logging its value, pushed immutable API/worker image digests, applied the full ECS/ALB/SQS/DynamoDB/S3/WAF stack, and attached the Vercel project to the custom frontend domain. The API health endpoint returns HTTP 200 and the ALB target is healthy.

**Evidence:** AWS Route 53/ACM/ECR/Secrets Manager state, `infra/terraform/hackathon.tfvars` (ignored), and the successful targeted Terraform apply.

### Benchmarks and product verification — July 18–21, 2026

The fixture release gate now runs seven cases: the UCI Bank flagship, multi- and single-mechanism planted cases, semantic proxy, suspicious hard negative, and two clean controls. Captured schema-v2 output reports six exact expected feature/mechanism pairs, zero false confirmations/negatives, precision/recall `6/6` with Wilson interval `[0.609657, 1.0]`, exact pair match `7/7`, useful questions `6/7`, and zero degradation/schema failures. The flagship reproduces ROC AUC `0.8713005400607956` and corrects to `0.7330845871361364`. Fixture tokens/cost remain explicitly zero.

**Evidence:** `src/polygraphml/benchmarks/`, `benchmark-results/latest.json`, `docs/BENCHMARKS.md`, and `tests/test_benchmark_evaluation.py`.

### Operational evidence tooling — July 19, 2026

Codex added a measured queue-timing calibrator, a fail-closed historical live-smoke recorder, a new exactly-three-case v0.2 live evaluator, and a public-path deployed-smoke recorder. The calibrator distinguishes fixture evidence from a production-calibrated sample. The recorders remove dataset sample values before model calls and write metadata only—never event payloads, prompts, reasoning text, raw values, session tokens, or credentials.

**Evidence:** `src/polygraphml/operations/`, `src/polygraphml/benchmarks/live_evaluate.py`, `benchmark-results/queue-timing.json`, `benchmark-results/deployed-smoke.json`, `tests/test_operations.py`, `tests/test_live_evaluation.py`, `make calibrate-queue`, `REF=<sha> make public-github-gate`, `make eval-live`, `make deployed-smoke`, and `make deployment-preflight`.

## Verification record

| Gate | Result |
|---|---|
| v0.2 Ruff/mypy checks | Passed across 46 source files; final post-doc `make check` rerun pending |
| Backend suite | 82 passed; 80.57% branch-aware coverage (verified in two process shards within the local execution window) |
| Frontend lint/type/unit/build | Passed; 6 unit/component tests |
| v0.2 Playwright workflow | 6 passed: SSE failure/fallback, refresh/replay, provenance-gated live label, reports, repair download, clean clearance, axe, and three responsive sizes |
| v0.2 fixture benchmark | 7 cases; 6/6 pairs; 0 false confirmations/negatives; two clean controls |
| Terraform 1.14.3 init/validate | Passed with AWS provider 6.55.0 and current build/IAM changes |
| Production npm audit | Passed with zero production vulnerabilities |
| API/worker container build | v0.2 candidate images build; OCI version/revision labels and containerized API health/version were verified locally |
| Gitleaks/workflow/CI | Historical earlier-slice pass; v0.2 clean-history CI remains open |
| AWS API and Vercel domains | Historical deployment responds; exact v0.2 `/version`/frontend SHA verification remains open |
| Live OpenAI evaluation | Historical single case passed; new exactly-three-case v0.2 gate remains open |
| GitHub Actions PR CI | Historical run `29714407361` passed; a new v0.2 PR/Terra review is required |

## Remaining submission work

- Publish the expectation commit, import the flagship through public GitHub at that immutable SHA, and run `make eval-live` exactly once.
- Open the v0.2 PR to `dev`, pass clean-checkout CI and GPT-5.6 Terra review, merge through `main`, and tag `v0.2.0`.
- Deploy frontend/backend from one SHA and pinned digests; repeat public smoke, repair download, replay/resume, deletion, and resilience gates.
- Rotate the OpenAI key, update Secrets Manager/local ignored configuration, redeploy the worker, and repeat secret/history scanning.
- Record and verify the live demo, labeled fixture fallback, and submission metadata.

## Debugging log

Add short, specific entries as real issues occur:

| Date | Symptom | Root cause | Codex contribution | Verification |
|---|---|---|---|---|
| 2026-07-18 | API returned 500 while creating benchmark audits | Repository persisted objects under a parent ID instead of each object's canonical ID | Corrected identity mapping and added lifecycle coverage | Full audit lifecycle passes |
| 2026-07-18 | Duplicate/stale worker processing could collide on event sequence | Event emission trusted a stale in-memory sequence | Derived the next sequence from persisted state and tested duplicate delivery | Queue/idempotency tests pass |
| 2026-07-18 | Presigned browser upload would send API auth to S3 | Client treated every upload URL as an API-relative path | Split local and absolute upload behavior; signed headers only for S3 | Frontend upload regression tests pass |
| 2026-07-18 | Playwright intermittently saw the API as unavailable and labeled mode live | Vite was ready before FastAPI and null readiness fell through to the live badge | Added neutral connecting state, readiness retries, and stack readiness wait | Four Playwright tests pass |
| 2026-07-18 | Secret scan flagged deterministic SQLite WAL state | Directory scan included ignored runtime artifacts | Added a narrow path allowlist while preserving source/history scanning | Worktree and history report no leaks |
| 2026-07-19 | Live plan could name a valid-schema mechanism the P0 coordinator did not execute | Output schema was broader than the shipped primary semantic probe | Constrained the primary plan to post-outcome availability and reconstructed model features | Invalid plans now degrade visibly; mocked live orchestration passes |
| 2026-07-20 | Disposable deployed audits could stall after a retry | A stale audit checkpoint could lower DynamoDB's event counter and collide with an existing event | Made the counter monotonic, synchronized transition state, and added retry regression coverage | Public API → SQS → worker live smoke completes and replays 26 events |
| 2026-07-20 | Disposable project deletion returned 500 in AWS | API task role lacked `dynamodb:BatchWriteItem`, used by durable project cleanup | Added the narrowly scoped DynamoDB permission and verified deletion through the public API | Deployed smoke deletes its project; no disposable project/audit records remain |
| 2026-07-20 | Queue timeout was justified only by fixture timings | Live model/network variability was not yet represented in the calibration | Added a 20-run public-path timing capture and extended the calibrator to consume deployed-smoke outputs | P95 32.666s; 300-second visibility / 60-second heartbeat exceed the 161-second recommendation |
| 2026-07-20 | An interrupted event writer could leave the counter behind an existing durable event | A conditional event insert then collided and crashed the worker | Retried only the sequence-allocation collision; deployed the worker hardening and exercised a controlled missing-project fault | Three retries reached `PROJECT_NOT_FOUND` DLQ; audit ended `failed_partial`/`dead_lettered`; metadata-only evidence is retained |
| 2026-07-20 | Production cold start had not been demonstrated against the worker-only live secret boundary | Earlier smoke runs used an already-running worker | Scaled the worker to zero, waited for zero running tasks, started a fresh worker, and ran the public live smoke | The cold-start smoke completed with replay, question/resume, and disposable-project deletion evidence |
| 2026-07-20 | PRs could reach `dev` with only deterministic CI checks | No semantic review gate existed for changes that passed lint and tests | Added a bounded, fail-closed `gpt-5.6-terra` review workflow that reads patches but never executes PR code with the OpenAI secret | Unit tests cover review policy and comment rendering; GitHub branch protection activation remains a repository setting |
| 2026-07-20 | Required PR status checks could not be enabled on `dev` | GitHub rejected branch protection for the current private repository plan | Configured the repository Actions secret and documented the workflow/plan limitation without weakening workflow security | GitHub API returned HTTP 403; upgrade to Pro or make the repository public before enforcing the status check |
| 2026-07-20 | Frontend CI could not launch its local API stack | The frontend job had no Python environment, then cold GitHub runners exceeded the original ten-second API readiness window | Installed the pinned backend environment in the frontend job, serialized E2E environment setup, captured service logs on failure, and allowed a bounded 30-second cold start | GitHub Actions run `29714407361` passed all four CI jobs, including Playwright E2E |
| 2026-07-21 | E2E startup crashed on persisted audits after the metric provenance schema changed | Old `MetricValue` payloads lacked v2 protocol/tier fields, and the test stack reused one SQLite file | Added an explicit legacy read migration to `legacy_*`/`static_only`, a regression test, and isolated temp state per Playwright run | Repository tests and six Playwright cases pass |
| 2026-07-21 | The frontend stayed in “Connecting” and raised a global error locally | `/version` was not included in the Vite proxy | Added the `/version` proxy and API contract coverage | Readiness/build badge appears and E2E passes |
| 2026-07-21 | Mobile intake overflowed by 194 px | The build badge and 610 px stepper minimum expanded the document rather than an internal scroller | Hid build detail at mobile width, constrained the header, and made the stepper a bounded scroll container | Mobile overflow assertion passes at 390×844 |
| 2026-07-21 | Repair download would fail in AWS despite successful bundle creation | The API task role lacked `s3:GetObject` needed by its presigned GET | Added the narrow permission plus S3 presign coverage and exact release/build Terraform inputs | Terraform validates and AWS adapter tests pass |

## Division of labor

David owns product intent, scope approval, API credentials, deployment accounts, risk acceptance, and final submission. Codex supports design critique, implementation, tests, debugging, documentation, and verification within that direction. All generated work is reviewed, and completion claims require reproducible evidence.

## Logging rules

- Never include the OpenAI API key or any credential value.
- Do not paste raw user datasets, private prompts, or presigned URLs.
- Record exact commands and summarized results, not fabricated green checks.
- Link each major claim to a commit, file, test, trace, or deployment.
- Keep fixture-mode and live-model results clearly distinguished.
