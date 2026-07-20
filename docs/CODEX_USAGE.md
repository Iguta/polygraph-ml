# How Codex Is Building PolygraphML

This is an evidence log for the OpenAI Build Week submission. It must describe completed work truthfully. Planned work stays labeled **planned** until the referenced implementation and verification exist.

## Codex session IDs

- Active Codex thread: `019f77f9-27da-7560-b2ea-9b42e521ad49` (captured from the active goal metadata).

## Git references

- Starting documentation commit: `a4291caadc53fe27c7fefbda501f29076d52b227` (`docs: PolygraphML starter documentation suite`).
- Implementation commit: `0d8f00caefb6150ff3d86d30396c478a030612d9` (`feat: ship PolygraphML audit platform`).
- Release-branch CI hardening: `2e3ee05`, `fa11d28`, `f738301`, and `e924c84`.
- Review PR: [#1 — `agent/polygraphml-release` into `dev`](https://github.com/Iguta/polygraph-ml/pull/1) (draft while deterministic CI is complete).

## Current repository state

As of July 20, 2026, the repository contains a functional local fixture-mode vertical slice, deterministic audit engine, polished React workflow, AWS infrastructure definitions, container images, and benchmark release gate. AWS and Vercel authentication pass. The delegated `polygraphml.davidiguta.com` zone resolves, the ACM certificate is issued, the pinned AWS stack is applied, and the API/worker services are healthy on ECS Fargate. The React production site responds at `https://polygraphml.davidiguta.com`. A sanitized live GPT-5.6 trace was rerun after the committed benchmark expectations. The implementation is committed and under review in PR #1; demo-video and submission-metadata work remain David-owned.

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

### Agent and human loop — July 18, 2026

Codex pinned the OpenAI and Agents SDKs, configured explicit `gpt-5.6-sol` Responses API execution, typed read-only agent tools, structured investigation output, bounded timeouts/fallback, and separate rationale summaries. Fixture mode proves the persisted question/resume and policy path without claiming a model call. Live mode remains unverified until a key is configured and a sanitized trace is captured.

**Evidence:** `src/polygraphml/agent/runtime.py`, `src/polygraphml/worker/coordinator.py`, and `tests/test_audit_lifecycle.py`.

### AWS and Vercel definitions — July 18, 2026

Codex added Docker images and Terraform for S3, DynamoDB, SQS/DLQ, Secrets Manager, ECR, ECS Fargate, IAM, CloudWatch, ALB TLS, and Route 53. Terraform validation and both local container builds pass. The browser's presigned-upload regression test proves that the session bearer token is not sent to S3. The stack is deployed and its public health surfaces are verified.

**Evidence:** `infra/terraform/`, `Dockerfile.api`, `Dockerfile.worker`, `docs/DEPLOYMENT.md`, `tests/test_aws_adapters.py`, and `frontend/src/api.test.ts`.

### Cloud deployment — July 19–20, 2026

Codex verified the `PolygraphMLDeployer` AWS identity and Vercel CLI authentication, created and delegated the Route 53 zone for `polygraphml.davidiguta.com`, validated the ACM certificate for `api.polygraphml.davidiguta.com`, created ECR repositories and the Secrets Manager container with Terraform, stored the OpenAI key in Secrets Manager without logging its value, pushed immutable API/worker image digests, applied the full ECS/ALB/SQS/DynamoDB/S3/WAF stack, and attached the Vercel project to the custom frontend domain. The API health endpoint returns HTTP 200 and the ALB target is healthy.

**Evidence:** AWS Route 53/ACM/ECR/Secrets Manager state, `infra/terraform/hackathon.tfvars` (ignored), and the successful targeted Terraform apply.

### Benchmarks and product verification — July 18, 2026

The fixture release gate runs isolated post-outcome and group-contamination cases, a planted multi-mechanism campaign case, and a licensed public UCI COVID-19 surveillance clean control. Captured output reports four true positives, precision/recall `1.0`, zero false confirmations/negatives, zero reproduction and corrected-metric error, and corrected campaign AUC `0.8627956989247312`. Fixture token use and cost are explicitly zero.

**Evidence:** `src/polygraphml/benchmarks/`, `benchmark-results/latest.json`, `docs/BENCHMARKS.md`, and `tests/test_benchmark_evaluation.py`.

### Operational evidence tooling — July 19, 2026

Codex added a measured queue-timing calibrator, a fail-closed local live-smoke recorder, and a public-path deployed-smoke recorder. The calibrator distinguishes fixture evidence from a production-calibrated sample. The smoke recorders reject fixture degradation where required, remove dataset sample values before model calls, exercise durable worker processing, and write counts/identifiers only—never event payloads, prompts, reasoning text, raw values, session tokens, or credentials.

**Evidence:** `src/polygraphml/operations/`, `benchmark-results/queue-timing.json`, `benchmark-results/deployed-smoke.json`, `tests/test_operations.py`, `make calibrate-queue`, `make live-smoke`, `make deployed-smoke`, and `make deployment-preflight`.

## Verification record

| Gate | Result |
|---|---|
| Ruff format/lint and mypy | Passed |
| Backend tests with coverage | 48 passed; 81.27% total coverage |
| Frontend lint/type/unit/build | Passed; 5 unit/component tests |
| Playwright fixture workflow | Passed with refresh, resume, report, axe checks, and three responsive sizes |
| Terraform 1.14.3 init/validate | Passed with AWS provider 6.55.0 |
| API and worker Docker builds | Passed as local `:test` images |
| Gitleaks worktree and Git history | Passed with redaction; no leaks found |
| GitHub Actions workflow lint | Passed with actionlint 1.7.7 |
| AWS API health and ALB target | Passed; `https://api.polygraphml.davidiguta.com/healthz` returned HTTP 200 |
| Vercel custom domain | Passed; `https://polygraphml.davidiguta.com` returned HTTP 200 |
| Live OpenAI smoke | Passed; sanitized trace recorded with 23 events and model `gpt-5.6-sol` |
| GitHub Actions PR CI | Passed in run `29714407361`: backend, frontend including Playwright E2E, Terraform validation, and history secret scanning |

## Remaining submission work

- Mark PR #1 ready for review to run the configured GPT-5.6 Terra reviewer, then merge after acceptance.
- Retain the completed cold-start, refresh/replay, partial-failure, deletion, and DLQ metadata-only evidence for final review.
- Record and verify the final demo video, fallback recording, and submission metadata.

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

## Division of labor

David owns product intent, scope approval, API credentials, deployment accounts, risk acceptance, and final submission. Codex supports design critique, implementation, tests, debugging, documentation, and verification within that direction. All generated work is reviewed, and completion claims require reproducible evidence.

## Logging rules

- Never include the OpenAI API key or any credential value.
- Do not paste raw user datasets, private prompts, or presigned URLs.
- Record exact commands and summarized results, not fabricated green checks.
- Link each major claim to a commit, file, test, trace, or deployment.
- Keep fixture-mode and live-model results clearly distinguished.
