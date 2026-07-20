# AGENTS.md — PolygraphML Repository Instructions

This file applies to the entire repository. A more deeply nested `AGENTS.md` may add directory-specific instructions later, but it must not weaken the product, evidence, security, or secret-handling invariants defined here.

## 1. Product north star

PolygraphML is an evidence-backed QA system for machine learning models. It audits the trained model, dataset, and training/evaluation pipeline together, preferably using the original Jupyter notebook or pinned GitHub repository.

The core operating principle is:

> **The model reasons; code computes; evidence decides.**

Every implementation decision should support a trustworthy comparison among:

1. **Reported** — the metric claimed by the submitted notebook, repository, or user.
2. **Reproduced** — the metric obtained by rerunning or reconstructing the submitted evaluation.
3. **Corrected** — the metric obtained after applying the smallest justified repair to a confirmed evaluation or leakage defect.

Do not reduce the primary product to dataset profiling. Dataset-only input may receive a clearly labeled preflight, but it is not a complete model audit.

## 2. Canonical documents

Read the documents relevant to the task before changing behavior:

- `README.md` — project overview and current status.
- `docs/BRD.md` — business goals, success criteria, and risks.
- `docs/PRD.md` — product requirements and MVP acceptance criteria.
- `docs/TDD.md` — domain model, audit engine, finding policy, and security design.
- `docs/SOLUTION_ARCHITECTURE.md` — Vercel/AWS topology and trust boundaries.
- `docs/API_CONTRACT.md` — authoritative API and event schemas.
- `docs/PRODUCT_FLOW.md` — required React experience and states.
- `docs/IMPLEMENTATION_PHASES.md` — ordered implementation gates and Definition of Done.
- `docs/ROADMAP.md` — post-MVP direction and deferred scope.
- `docs/BUILD_PLAN.md` — hackathon critical path and cut lines.
- `docs/DEMO_SCRIPT.md` — target narrative; example metrics are not verified results.
- `docs/CODEX_USAGE.md` — evidence-backed Codex implementation log.

When documents conflict, use this precedence for implementation details:

1. `docs/API_CONTRACT.md` for transport shapes and invariants.
2. `docs/TDD.md` for domain behavior and finding policy.
3. `docs/PRD.md` for user-facing requirements and scope.
4. `docs/SOLUTION_ARCHITECTURE.md` for deployment and trust boundaries.
5. `docs/IMPLEMENTATION_PHASES.md` for sequencing and release gates.

Do not silently choose between material conflicts. Resolve the documents in the same change or ask for direction when the choice changes product intent.

## 3. Current-state honesty

The repository is specification-first until implementation files and passing verification prove otherwise.

- Never describe planned code, tests, deployment, benchmarks, or UI as completed.
- Do not mark a DoD checkbox complete without reproducible evidence.
- Do not place illustrative demo numbers into production fixtures as though they were measured.
- Label fixture-mode, mocked, replayed, and live-model results distinctly.
- Update `docs/CODEX_USAGE.md` only with real files, commands, commits, tests, traces, deployments, or debugging events.
- Preserve `TODO` items that remain unresolved; do not replace them with invented details.

## 4. MVP scope and cut discipline

The P0 vertical slice is:

- a model plus evaluation dataset plus notebook/repository evidence;
- tabular binary classification;
- public GitHub or safe upload/benchmark intake;
- `.skops` as the primary model path;
- one `gpt-5.6-sol` audit agent with typed deterministic tools;
- one material human follow-up question and resume path;
- reported/reproduced/corrected metrics;
- a replayable Decision Trace;
- SQS-backed durable execution;
- a polished React/Vercel frontend and AWS backend;
- planted-leak tests, a clean control, and one pinned public benchmark.

Implement P0 work in the order defined by `docs/IMPLEMENTATION_PHASES.md`. Do not pull P1/P2 work forward while a P0 gate is incomplete. Follow the cut order in `docs/BUILD_PLAN.md` when time is constrained.

## 5. OpenAI integration

- OpenAI is the initial model provider.
- Use the OpenAI Agents SDK as the primary agent runtime and the Responses API model path.
- Configure the audit agent explicitly with `gpt-5.6-sol`; do not depend on an SDK default model.
- The official `openai` SDK may be used directly for lower-level calls when that is simpler than the agent runtime.
- The MVP uses one audit agent. Do not introduce handoffs, agent swarms, debate, or specialist agents without benchmark evidence and an architecture decision.
- Use structured schemas for hypotheses, questions, tool requests, finding transitions, and reports.
- Bound retries, timeouts, token use, and live API costs.
- Deterministic analysis must remain usable when a model call fails.
- Do not run broad live-model load tests or expensive evaluation sweeps unless the user explicitly authorizes the scope and cost.

## 6. Transparency and evidence rules

Do not claim to expose raw chain-of-thought or private reasoning tokens.

The user-visible **Decision Trace** may include:

- scenario facts and assumptions;
- user questions and answers;
- falsifiable hypotheses and concise rationale summaries;
- requested probes and falsification conditions;
- typed tool starts/results;
- compute-owned evidence and source references;
- corrections and finding-status changes;
- optional labeled reasoning summaries;
- retries, warnings, limitations, and errors;
- model/evaluator/schema versions, hashes, and timestamps.

Reasoning summaries are narration, not deterministic evidence. Developer traces and user-visible events are separate surfaces and must be sanitized independently.

## 7. Finding and metric invariants

Use these finding statuses exactly unless the canonical contracts are intentionally migrated together:

`needs_context | suspected | tested | confirmed | cleared | inconclusive`

Rules:

- Semantic suspicion never confirms a defect.
- A large ablation delta shows model reliance; it does not by itself prove leakage.
- `confirmed` requires the mechanism and scenario to be established, deterministic supporting evidence, contradictory evidence addressed, and measured impact or a clearly documented protocol-invalidating condition.
- `cleared` applies only to the tested mechanism under the declared scenario.
- Unsupported or timed-out checks become visible limitations or `inconclusive`, never silent clearances.
- Severity, confidence, and status are separate concepts.
- Every conclusion states what evidence or scenario change could alter it.

Only versioned compute code may populate numeric fields in `Evidence`, `MetricComparison`, and quantitative verdicts. Model-generated prose may cite those values but may not create or overwrite them.

## 8. Artifact and execution safety

Treat every repository, archive, notebook, dataset, and model artifact as untrusted.

Initially supported:

- datasets: CSV and Parquet;
- notebooks/source: `.ipynb` and inspected Python source;
- scikit-learn: `.skops` after untrusted-type inspection;
- XGBoost: validated `.json`/`.ubj` when the adapter is implemented;
- ONNX: limited inference/evaluation only when feature order and preprocessing metadata are explicit.

Required rules:

- Arbitrary JSON is metadata, not automatically a model.
- Never load remotely supplied pickle, joblib, cloudpickle, or similar executable serialization.
- Never execute submitted code in the API process or agent-coordinator process.
- Static repository/notebook inspection must not import the submitted code.
- If submitted code execution is implemented, use a separate disposable task with no OpenAI key, no production credentials, narrow S3 permissions, restricted egress, resource/time limits, and a fresh workspace.
- Reject archive path traversal, absolute paths, symlinks, device files, and expansion bombs.
- Resolve Git refs to immutable commit SHAs before analysis.
- Prefer a partial/static audit over weakening an isolation boundary.

## 9. Secrets, privacy, and logging

- Never print, return, log, commit, screenshot, or paste the OpenAI API key.
- Local live mode reads `OPENAI_API_KEY` from the ignored `.env`; `.env.example` contains names only.
- Never use `cat .env`, include `.env` in tool output, or read the secret value merely to verify setup. Check only file status and whether the named variable is non-empty.
- AWS production reads the key from Secrets Manager through the coordinator task role.
- The browser, Vercel bundle, API responses, SQS messages, audit events, exports, and executor tasks must never receive the key.
- SQS messages contain identifiers, schema/idempotency metadata, and S3 references only—not artifact bytes, full prompts, or secrets.
- Do not log raw dataset rows, presigned URLs, authentication tokens, private source, or unsanitized model/tool payloads.
- Keep uploaded-artifact retention explicit and time-bounded.
- Run secret scanning before deployment or submission and inspect Git history, not only the working tree.

If a secret is exposed, stop work that could propagate it, tell the user exactly where it appeared, and recommend revocation/rotation. Do not repeat the secret in the report.

## 10. AWS and asynchronous execution

- The API persists audit state before enqueueing an SQS job.
- Assume SQS at-least-once delivery. Every worker operation and state transition must be idempotent.
- Use conditional leases/checkpoints in DynamoDB.
- Extend message visibility while a worker is active and delete only after a committed terminal or intentional pause checkpoint.
- A user-question pause persists `waiting_for_user`, releases the job, and uses a new idempotent resume message after the answer.
- Bound retries; exhausted retryable jobs enter a DLQ and produce an observable alarm.
- Store large/immutable artifacts and results in S3; store project/audit state and ordered events in DynamoDB.
- SSE must resume from a last event ID and have a tested polling fallback.
- Browser disconnect or refresh must not cancel or lose an audit.
- Use least-privilege IAM and infrastructure as code.

## 11. API and schema discipline

- Treat `docs/API_CONTRACT.md` as the API source of truth until generated schemas become authoritative.
- Reject unknown write fields by default.
- Use typed request, response, domain, tool, and event models.
- Preserve response envelopes, error codes, idempotency behavior, event ordering, and provenance fields.
- Do not change a public schema in only one layer. Update backend model, generated/shared frontend type, contract test, fixtures, API documentation, and affected UI together.
- Prefer additive versioned migrations over ambiguous field reuse.
- Keep user-visible payloads sanitized separately from internal state.

## 12. Frontend quality bar

The React application is a judged product, not an administrative afterthought.

- Implement every state and edge flow in `docs/PRODUCT_FLOW.md`.
- Establish and reuse design tokens/components for type, spacing, color, motion, status, and focus.
- Make assumptions, model summaries, deterministic evidence, and conclusions visually distinct.
- Show supported/limited/unsupported artifact status before audit start.
- Every long-running state explains what is happening and remains resumable.
- Support keyboard navigation, visible focus, semantic labels, sufficient contrast, and reduced motion.
- Verify mobile, laptop, and 1080p recording layouts.
- Never sacrifice provenance or qualification to make a metric animation more dramatic.

## 13. Benchmark and test rules

Expected benchmark findings must be declared and versioned before the live audit is run.

Every admitted public benchmark requires source, license, hashes, model, dataset, notebook/pipeline, scenario, expected findings, tolerance, limitations, and prohibited claims. A COVID-19 case must not enter the demo until provenance, licensing, reproducibility, and clinical-claim boundaries pass review.

Required verification should grow with the implementation:

- unit tests for adapters, parsers, probes, finding policy, state transitions, and sanitization;
- property tests for path/archive validation and idempotency invariants;
- API and structured-output contract tests;
- integration tests for S3, DynamoDB, SQS, retries, and event replay;
- synthetic single-leak, multi-leak, and clean-control benchmarks;
- a pinned public model + data + notebook/repository benchmark;
- Playwright coverage of intake, mapping, question/resume, refresh/replay, verdict, and report.

A false `confirmed` finding on the clean control is release-blocking. Do not change expected outputs after a failure merely to make the suite green.

## 14. Repository workflow

- Inspect the repository and relevant canonical docs before editing.
- Preserve unrelated user changes and work carefully in a dirty worktree.
- Keep changes scoped to the requested phase or behavior.
- Prefer small, reviewable modules with explicit boundaries over speculative frameworks.
- Do not add dependencies without a concrete need; pin direct dependencies and record why high-risk/runtime dependencies exist.
- Do not commit, push, open a pull request, deploy, or mutate external systems unless the user asks for that action.
- Do not rewrite Git history or use destructive cleanup commands.
- Update documentation and `docs/CODEX_USAGE.md` in the same change when implementation makes an existing statement stale.

## 15. Commands and verification

No build commands are authoritative until the scaffold that implements them exists. Do not invent successful command output.

The target top-level interface is:

```text
make dev        # local frontend, API, and worker/substitutes
make format     # format supported languages
make lint       # lint without mutation where practical
make typecheck  # Python/TypeScript static checks
make test       # unit and contract tests
make check      # all non-deployment release checks
```

When creating the scaffold, either implement these commands or update this section and the README together. Before handoff, run the smallest relevant checks first, then the broader release check in proportion to the change. Report exactly what ran, what passed, what failed, and what was not run.

Documentation-only changes require at minimum:

- `git diff --check`;
- validation of internal document links;
- a search for stale terminology or contradictory status/metric names;
- confirmation that no secret value entered the diff.

## 16. Completion standard

A task is not complete merely because code was written. Completion requires:

- requested behavior implemented at the correct architectural boundary;
- relevant tests and failure paths exercised;
- security and evidence invariants preserved;
- user-visible states and errors handled;
- documentation/contracts updated;
- no known release-blocking regression;
- an honest handoff describing verification and remaining limitations.

Use `docs/IMPLEMENTATION_PHASES.md` as the release checklist. If a required item cannot be completed, leave it unchecked and state the blocker or deliberate scope cut.
