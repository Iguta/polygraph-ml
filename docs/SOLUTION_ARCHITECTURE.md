# Solution Architecture — PolygraphML

**Version:** 1.1 · **Owner:** David · **Date:** July 18, 2026

## 1. Architecture at a glance

```text
┌──────────────────────────────────────────────────────────────────┐
│                       Vercel: React frontend                      │
│ Source intake · artifact map · Decision Trace · verdict · report │
└──────────────────────┬────────────────────────────▲──────────────┘
                       │ HTTPS / SSE                │
                       ▼                            │
┌──────────────────────────────── AWS ──────────────────────────────┐
│                                                                  │
│  ┌─────────────────────┐       ┌──────────────────────────────┐  │
│  │ FastAPI API service │──────▶│ S3: uploads and result files │  │
│  │ on ECS Fargate      │       └──────────────────────────────┘  │
│  │ validation · REST   │                                         │
│  │ event replay · SSE  │──────▶┌──────────────────────────────┐  │
│  └──────────┬──────────┘       │ DynamoDB: projects, audits,  │  │
│             │                  │ questions, ordered events    │  │
│             ▼                  └──────────────▲───────────────┘  │
│  ┌─────────────────────┐                       │                  │
│  │ SQS audit queue     │                       │                  │
│  │ + dead-letter queue │                       │                  │
│  └──────────┬──────────┘                       │                  │
│             ▼                                  │                  │
│  ┌─────────────────────────────────────────────┴───────────────┐  │
│  │ Audit coordinator worker on ECS Fargate                    │  │
│  │ OpenAI Agents SDK · artifact adapters · deterministic tools │  │
│  │ one GPT-5.6 audit agent · idempotent state machine          │  │
│  └──────────────┬───────────────────────────────┬──────────────┘  │
│                 │                               │                 │
│                 │ safe compute                                    │
│                 ▼                                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ pandas · PyArrow · scikit-learn · skops probes/corrections │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Secrets Manager: OpenAI key   CloudWatch: logs/metrics/alarms   │
└───────────────────────────┬──────────────────────────────────────┘
                            │ Responses API
                            ▼
                  ┌──────────────────────┐
                  │ OpenAI: gpt-5.6-sol │
                  └──────────────────────┘
```

## 2. Stack

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | React + TypeScript + Vite, deployed to Vercel | Fast, polished SPA with strong component and test ergonomics |
| API | Python 3.14 + FastAPI on ECS Fargate | Shared Python domain types, streaming, and long-running backend control |
| Agent | OpenAI Agents SDK; official `openai` SDK for direct calls | Managed tool loop, structured output, tracing, and Responses API access |
| Primary model | `gpt-5.6-sol` | Central semantic reasoning and investigation planning |
| Queue | Amazon SQS + DLQ | Durable asynchronous audits, retries, and browser-independent execution |
| Artifact storage | Amazon S3 with presigned upload/download URLs | Large files bypass API containers; retention and encryption controls |
| State/event store | Amazon DynamoDB | Durable audit state and ordered event replay without server affinity |
| Compute | pandas, PyArrow, scikit-learn, skops; limited XGBoost/ONNX descriptors | Initial safe adapter and deterministic probe surface |
| Secrets | AWS Secrets Manager + ECS execution role injection | Server-side OpenAI key without source-control or browser exposure |
| Observability | CloudWatch plus sanitized OpenAI/Agents SDK traces | Operational debugging while controlling sensitive payload capture |
| Edge protection | ALB TLS + AWS WAF per-IP API/session rate limits | Public demo abuse resistance before application session quotas |
| Testing | pytest, contract tests, synthetic/public benchmarks, Playwright | Unit correctness, ground-truth evaluation, and demo-path confidence |

Exact Python and npm versions are pinned in `uv.lock` and `frontend/package-lock.json`.

## 3. Service responsibilities

### React frontend

Creates projects, obtains presigned uploads, maps artifacts, captures the scenario contract, starts audits, resumes the Decision Trace, answers questions, and renders/export results. It never receives an OpenAI key and never calls OpenAI directly.

### FastAPI service

Validates metadata, issues scoped presigned URLs, persists project/audit state, enqueues jobs, exposes replayable events over SSE with polling fallback, accepts follow-up answers, and serves result manifests. The API does not execute notebooks or load submitted model objects.

### SQS

The queue decouples user requests from audit duration. Messages contain only identifiers, artifact references, requested operation, and idempotency metadata. They never contain artifact bytes, raw API keys, or full prompts. Visibility timeout, heartbeat/extension, bounded retry count, and a DLQ are configured. Twenty metadata-only deployed live durations produced a 32.666-second P95 and a 161-second recommendation; the configured 300-second lease and 60-second heartbeat cover that sample and must be recalibrated after materially larger workloads.

### Audit coordinator worker

Consumes one audit job, obtains artifact metadata, runs the single audit agent, invokes typed deterministic tools, emits ordered events, and checkpoints the state machine. Duplicate delivery is expected and neutralized using conditional DynamoDB state transitions and idempotent result keys.

The coordinator may access the OpenAI key but does not execute arbitrary submitted Python. Safe model adapters deserialize only formats approved by policy.

### Isolated executor (P1, not deployed)

Notebook or repository code execution is a separate capability. When enabled, a disposable task receives a narrow S3 input/output scope, no OpenAI key, no production credentials, restricted or disabled egress, a read-only base image, resource/time limits, and a fresh workspace. Arbitrary dependency installation is not part of the hackathon MVP. If execution cannot be performed safely, the audit reports a partial reproduction instead of weakening isolation.

## 4. OpenAI integration

OpenAI is the initial provider. The coordinator uses the OpenAI Agents SDK, which uses the Responses API by default, with `gpt-5.6-sol` explicitly configured. A narrow internal provider interface avoids spreading SDK calls through the codebase, but multi-provider routing is not an MVP requirement.

The agent receives profiles, source excerpts, scenario facts, and deterministic tool results. Full raw datasets are not sent to the model. Structured outputs capture hypotheses, questions, probe plans, finding updates, and report text. Reasoning summaries may be requested for user narration; raw reasoning tokens are not exposed or treated as evidence.

## 5. Data flow

1. Browser creates a project and uploads artifacts directly to an encrypted S3 prefix using short-lived presigned URLs.
2. API records artifact checksums and validated metadata in DynamoDB.
3. Browser submits the scenario contract and starts an audit with an idempotency key.
4. API persists `queued`, sends an SQS message, and returns `202 Accepted`.
5. Worker claims the audit, reconstructs evidence, asks questions or runs probes, and appends ordered Decision Trace events.
6. The API supports SSE replay after the last event ID plus JSON polling; the current React client uses durable JSON polling and restores the active audit after refresh.
7. Corrections, findings, and Markdown reports are durable domain records in DynamoDB; submitted artifact bytes remain in S3.
8. Retention rules remove user artifacts after the configured period while preserving only permitted metadata.

## 6. Trust boundaries and invariants

- The browser is untrusted and has no cloud or OpenAI credentials.
- Uploaded artifacts are untrusted until type, size, checksum, and project-scope validation completes; archive formats are not accepted in P0.
- SQS delivery is at least once; all processing must therefore be idempotent.
- Model-authored numeric claims cannot populate metric fields.
- A user-visible event is sanitized independently from developer tracing.
- Submitted code never shares a process or credentials with the API or agent coordinator.
- A GitHub URL is pinned to a commit before analysis; mutable branch names are not sufficient provenance.
- Remote pickle-like formats are rejected, not “carefully loaded.”

## 7. Deployment topology

- Vercel hosts the production React build.
- AWS hosts the FastAPI and worker container images in ECR/ECS Fargate.
- An Application Load Balancer terminates HTTPS for the API and supports the SSE connection; DNS and certificates are configured separately.
- S3, DynamoDB, SQS/DLQ, Secrets Manager, CloudWatch, and least-privilege IAM roles are provisioned as infrastructure as code.
- CORS allows only the configured Vercel domains and localhost development origins.
- The initial worker count is one for cost and predictability; queue-depth scaling is a roadmap optimization.

## 8. Local development

Docker Compose runs frontend, API, a local worker, and local service substitutes where practical. Fixture mode does not require an OpenAI key. Live mode reads `OPENAI_API_KEY` from an ignored `.env`; tests must never echo it. AWS production uses the coordinator worker's ECS execution role only to inject the secret into that worker container; runtime AWS API permissions remain on the separate task role.

## 9. Architecture evolution

The stable extension points are artifact adapters, probe tools, correction strategies, benchmark definitions, and report renderers. Future changes—additional frameworks, private repositories, distributed training, CI gates, fairness, robustness, or drift—must extend these contracts rather than bypass the evidence and provenance model.
