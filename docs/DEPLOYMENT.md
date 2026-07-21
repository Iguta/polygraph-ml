# Deployment Runbook

The production topology is React on Vercel and FastAPI plus one audit coordinator worker on AWS ECS Fargate. S3 stores artifacts, DynamoDB stores durable state and ordered events, and SQS/DLQ carries identifier-only jobs. Terraform defines the AWS resources. The current hackathon deployment is verified through public API/frontend health checks, a metadata-only public-path smoke audit, cold-start, refresh/replay, question/resume, controlled partial-failure/DLQ, and disposable deletion drills recorded in `docs/IMPLEMENTATION_PHASES.md`.

## Prerequisites

- an AWS account with a default VPC and public subnets in the selected region;
- a Route 53 public hosted zone and an API hostname in that zone;
- an issued ACM certificate covering that hostname;
- Docker, AWS CLI, and Terraform 1.14.3;
- a Vercel project for `frontend/`;
- a valid server-side OpenAI API key.

Run `make deployment-preflight` at any time. It reports only pass/open booleans for the key, AWS/Vercel authentication, deployment variables, sanitized live trace, Git review state, and fixture benchmark gate; it never displays credential or account values.

## 1. Bootstrap private registries and the secret

Copy `infra/terraform/terraform.tfvars.example` to an ignored `.tfvars` file and replace account, hostname, zone, certificate, and origin placeholders. The all-zero image digests are bootstrap placeholders only.

Initialize Terraform, then target only both ECR repositories and the Secrets Manager resource. Populate the secret value out of band; do not put it in Terraform variables, shell history, source files, build arguments, or Vercel.

## 2. Build and pin containers

Build `Dockerfile.api` and `Dockerfile.worker`, push both images to their Terraform-created ECR repositories, and resolve their immutable repository digests. Replace both placeholder image values with URIs ending in `@sha256:<64 hex characters>`.

Local image gates are:

```bash
docker build -f Dockerfile.api -t polygraphml-api:test .
docker build -f Dockerfile.worker -t polygraphml-worker:test .
docker compose config --quiet
```

## 3. Apply AWS infrastructure

```bash
cd infra/terraform
terraform fmt -check -recursive
terraform init
terraform validate
terraform plan -out polygraphml.tfplan
terraform apply polygraphml.tfplan
```

Terraform configures encrypted/versioned S3 storage with seven-day retention by default, DynamoDB point-in-time recovery and TTL, SQS redrive to a DLQ, CloudWatch queue alarms, TLS at the ALB, WAF per-IP API/session rate limits, least-privilege task roles, and separate ECS execution roles. Only the worker execution role may retrieve the OpenAI secret for environment injection; the API role cannot read it. Local fallback uploads are streamed with their declared byte limit instead of buffering an unbounded body.

## 4. Deploy Vercel

Import `frontend/` as the Vercel project root. Set `VITE_API_URL` to the Terraform `api_url` output and ensure `POLYGRAPHML_CORS_ORIGINS` matches the final Vercel origin before applying AWS. Build with `npm run build`; `frontend/vercel.json` supplies the single-page-app rewrite.

## 5. Production verification

Do not mark deployment complete until all of these are recorded against the public path:

- `/healthz` and `/readyz` succeed over TLS;
- a safe direct S3 upload completes without sending the session bearer token to S3;
- an audit survives browser refresh and resumes exactly once after a human answer;
- a deliberately exhausted retry reaches the DLQ and fires the alarm;
- deleting a disposable project removes state and artifacts;
- worktree and Git history secret scans pass;
- a real live-agent trace is sanitized and contains no raw chain-of-thought, artifact bytes, key, or presigned URL.

## Pull-request review gate

`.github/workflows/ai-pr-review.yml` runs only for non-draft pull requests targeting `dev`. It uses `gpt-5.6-terra` through the Responses API and fails closed on high/critical findings, model/API errors, oversized diffs, or potential credential material. The workflow uses `pull_request_target`, checks out only the trusted base SHA, and fetches PR patches from GitHub's API; it never executes PR code while the OpenAI secret is available.

Before enabling merges, add the repository Actions secret `OPENAI_API_KEY` and configure `gpt-5.6-terra` as a required status check in the `dev` branch protection rule. The reviewer covers up to four bounded textual chunks (40 files / 150,000 patch characters each), gives each provider request at most 90 seconds without automatic model-call retries, refuses approval if GitHub omits an unexpected patch, and posts one updatable PR comment. Textual generated contracts, client code, evidence, and any textual artifact patch GitHub supplies remain fully reviewable. Only a genuinely omitted patch at the exact large UCI table or binary `.skops` path uses the inventory path: the trusted base policy pins the release digests before the product PR; that PR must expose the same digest in a textual root-manifest patch; and the reviewer fetches both immutable Git blobs, strips only ASCII base64 whitespace, decodes strictly, enforces byte limits, scans for credentials, and requires the artifact SHA-256 to match both the reviewed manifest and pre-existing base-policy anchor. Changing either artifact therefore requires a separate policy/provenance review first. Their generator/derivation, safe-type inspection, and tests also remain in the review. It is a merge gate, not a substitute for human review.

The repository is public, so GitHub branch protection can require the `gpt-5.6-terra` status check before merging to `dev`.

Run the live smoke recorder only after configuring the ignored local key:

```bash
make live-smoke
```

It refuses fixture degradation and writes only model/audit identifiers, status, event/actor counts, confirmed mechanism names, and explicit redaction-policy flags to `benchmark-results/live-trace.json`. It never writes event payloads, prompts, sample values, reasoning text, or the key. Inspect the file before committing it.

To verify the deployed API, SQS worker, question/resume flow, event replay, and deletion boundary together, run a disposable benchmark audit:

```bash
API_URL=https://api.example.com make deployed-smoke
```

The result is metadata-only evidence in `benchmark-results/deployed-smoke.json`. The command deletes its disposable project even on a failed run; it never records the session token, event payloads, dataset values, prompts, or credentials.

After at least 20 deployed live audits, export their per-audit durations in the benchmark result shape and rerun `polygraphml-queue-calibration` with `mode: live`. Update the Terraform visibility timeout only from that captured recommendation.

## Retention and deletion

User artifacts expire from S3 after `artifact_retention_days` (default seven); noncurrent versions and incomplete uploads expire sooner. Session records use DynamoDB TTL. `DELETE /api/v1/projects/{project_id}` synchronously removes the project's artifacts and durable project/audit/event records. Local and mocked-AWS deletion behavior is covered by tests, and the recorded public deployed-smoke drill verifies disposable project deletion through the production API.
