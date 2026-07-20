# ADR-0003: Vercel, AWS, and SQS deployment topology

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

Audits outlive HTTP requests and browser sessions. The application needs a polished web delivery surface, durable asynchronous work, immutable artifact storage, replayable state, and a server-only OpenAI credential.

## Decision

Deploy the React frontend to Vercel. Run FastAPI and the audit coordinator on AWS ECS Fargate. Store artifacts/results in S3, project/audit/event state in DynamoDB, and secrets in Secrets Manager. Queue audit and resume operations through SQS with a DLQ. Stream persisted events through the API with polling fallback.

SQS messages contain identifiers and references only. Processing is idempotent because delivery is at least once. The API persists `queued` before enqueueing. A user-input pause checkpoints state and releases the message.

## Consequences

- Browser refresh does not cancel work.
- Infrastructure and local substitutes share domain contracts.
- IAM, retention, retries, visibility timeouts, DLQ alarms, and CORS are release concerns, not post-demo cleanup.
