# PolygraphML Hackathon-Winning Implementation Plan

## Summary

Turn the existing production-grade vertical slice into a defensible demonstration of the central thesis:

> The model reasons; code computes; evidence decides.

The release must prove three things in under three minutes:

1. GPT-5.6 discovers a semantic risk that profiling alone cannot establish.
2. Deterministic probes confirm or clear the mechanism and measure its impact.
3. PolygraphML produces a corrected metric and an actionable repair artifact.

`origin/main` and `origin/dev` already contain PR #1 at `22660b7`; the audit's "feature branch only" finding is stale. New work starts from `origin/main`, preserves the untracked `AUDIT.md`, and ends in a new tagged release.

## Implementation Changes

### 1. Unbox and evaluate the audit agent — P0

- Replace the forced `post_outcome`/`feature_availability` plan with a typed mechanism-to-probe registry supporting:
  - `post_outcome` → availability, association, correction;
  - `target_proxy` → provenance question, univariate association, ablation/correction;
  - `metric_mismatch` → metric-contract comparison;
  - existing split, group, and preprocessing checks remain deterministic automatic probes.
- Permit one to three ranked hypotheses and at most one material blocking question per audit. Every hypothesis must reference known features, a supported probe, assumptions, falsification conditions, and evidence sources.
- Refactor the coordinator from a hardcoded resume path into a probe dispatcher. Unsupported or incomplete hypotheses become `inconclusive`, never silently cleared.
- Add deterministic single-feature predictiveness evidence using train-only preprocessing and held-out ROC AUC. Treat association as reliance evidence, not leakage proof.
- Require semantic/provenance evidence plus deterministic measured impact before confirming post-outcome or target-proxy defects.
- Preserve one agent. Keep `gpt-5.6-sol`, Responses API, structured output, bounded turns, and explicit reasoning effort. Compare `high` against `medium` only through representative evals; do not add multi-agent, Pro mode, or programmatic tool calling without measured benefit.
- Record sanitized execution provenance: provider, live/fixture/degraded mode, requested model, resolved model returned by OpenAI, reasoning effort, harness version, token usage, latency, trace identifier, and prompt-schema version.
- Keep SDK developer traces separate from the user-visible Decision Trace and never expose raw chain-of-thought. Official guidance supports structured Agents SDK tracing for debugging and evaluation: [OpenAI tracing guidance](https://developers.openai.com/api/docs/guides/agents/integrations-observability#tracing).

#### Definition of Done

- [ ] A live agent independently selects at least two different supported mechanisms across predeclared cases.
- [x] The first v0.2 live gate independently selected the flagship `post_outcome:duration` hypothesis and material question without feature-name hardcoding.
- [x] A hard negative is cleared and no association score alone can produce `confirmed`.
- [x] Fixture degradation remains deterministic and visibly labeled.
- [x] Model-produced numbers cannot enter `Evidence`, `MetricComparison`, or verdict fields.
- [x] The sanitized v0.2 live record captures requested/resolved model, reasoning effort, token/latency counts, trace/response/request IDs, tool-result counts, mode, and failure code without payloads or chain-of-thought.

### 2. Strengthen intake, compute boundaries, and benchmarks — P0

- Introduce a versioned `.polygraphml.yml` manifest containing artifact paths, mappings, scenario defaults, feature descriptions, source references, license, and hashes. It must not encode the expected answer or whether a feature is leaking.
- Make GitHub import prefer the manifest, resolve the ref to a commit SHA, and fetch only referenced allowlisted artifacts. Keep bounded discovery as fallback.
- Add bounded compute subprocesses for already-approved `.skops` evaluation:
  - 120-second wall timeout;
  - 90-second CPU limit;
  - 2 GiB address-space limit;
  - bounded file descriptors/output;
  - single-thread numerical-library settings;
  - sanitized environment;
  - process-group termination on timeout.
- Describe this honestly as bounded compute, not a security sandbox. Notebook code remains static-only; a separate no-secret Fargate executor stays post-hackathon.
- Build the flagship external benchmark from the licensed [UCI Bank Marketing dataset](https://archive.ics.uci.edu/dataset/222/bank%2Bmarketing):
  - use the full pinned source or a reproducibly derived evaluation artifact;
  - train and publish a `.skops` model and notebook;
  - declare prediction before the current marketing call;
  - let the agent connect the documented current-call `duration` field to the scenario;
  - reproduce the submitted score, remove the unavailable field, and compute the corrected score.
- Add a synthetic semantic target-proxy case with an innocuous feature name and separately documented provenance.
- Add a suspicious-looking hard negative, such as a previous-campaign outcome that is genuinely available before the current decision.
- Retain the COVID case only as a small provenance/adapter clean-control smoke test; do not use it as the primary proof of benchmark quality.
- Extend benchmark output with raw numerators and denominators, confidence intervals where meaningful, per-case mechanism/feature accuracy, question usefulness, false confirmations, schema failures, degradation, tokens, latency, and cost.
- Add an ablation comparison:
  - deterministic-only identifies association but cannot establish semantics;
  - semantic-only proposes the risk but cannot confirm or calculate impact;
  - full PolygraphML establishes the scenario, computes evidence, and decides.

#### Definition of Done

- [x] Expected findings and prohibited claims are committed before any live evaluation (`16dd4c659f4f7f36507d40ff60fbc9280cb82cc5`).
- [x] The UCI benchmark imported and completed through the public GitHub path at `16dd4c659f4f7f36507d40ff60fbc9280cb82cc5`; the metadata-only record contains five verified artifacts and 27 events.
- [x] GitHub ref, tree, size, manifest, download-failure, traversal, and idempotency paths have automated tests.
- [x] A pathological estimator times out visibly as `inconclusive` without killing the worker.
- [x] Flagship and semantic-proxy defects are found and corrected.
- [x] Both clean controls have zero false `confirmed` findings.
- [x] Results report case counts rather than presenting "1.0 over four cases" as strong statistical proof.

### 3. Make the judged experience self-proving — P0

- Replace interval-only event fetching with authenticated `fetch`-based SSE streaming, `Last-Event-ID` replay, reconnect backoff, and tested polling fallback.
- Remove the global hardcoded GPT badge. Show `LIVE · gpt-5.6-sol` only when an audit's recorded execution provenance proves it; otherwise show `FIXTURE` or `DEGRADED`.
- Add build provenance to frontend and backend, including deployed commit SHA and release version. Expose an additive `/version` response and show the short SHA in the audit provenance panel.
- Fix the Docs navigation and use generated OpenAPI types as the frontend contract source. Remove unused runtime-schema dependencies unless they are actively used for response validation.
- Make report audiences real:
  - executive report: decision, business impact, corrected metric, limitations;
  - technical report: protocols, hashes, evidence, feature order, package versions, falsifiers.
- Add a deterministic repair bundle for supported literal feature-list notebooks:
  - `correction.json`;
  - unified notebook/source patch removing the confirmed feature;
  - corrected metric and protocol manifest;
  - README with limitations and rerun instructions.
  - If an exact patch cannot be produced safely, return `unavailable` with the reason rather than generating a speculative edit.
- Visually emphasize the semantic contribution, deterministic evidence, correction, and clean clearance as distinct stages.
- Update the demo to use a 90-second reliable proof path and retain a fully labeled fixture replay as recording fallback.

#### Public interface additions

- `ProbeKind` enum and mechanism/probe compatibility contract.
- `AgentExecutionProvenance` nested in audit provenance.
- Versioned `.polygraphml.yml` manifest schema.
- `GET /version` with release and build SHAs.
- `POST /api/v1/audits/{audit_id}/repair-bundle`, returning status, hashes, limitations, and a short-lived download URL.
- Benchmark result schema v2 with agent-quality and raw-count fields.
- All additions remain backward-compatible, reject unknown write fields, regenerate frontend types, and receive contract tests.

#### Definition of Done

- [x] Refresh or disconnect never loses the audit, question, or trace position.
- [x] UI mode/model/build labels agree with stored audit and deployment provenance.
- [x] Executive and technical reports differ materially and contain only compute-owned numbers.
- [x] The flagship audit downloads a valid, hash-addressed repair bundle.
- [x] Playwright covers live labeling, SSE reconnect, polling fallback, clean clearance, corrected comparison, provenance, and repair download.
- [x] Mobile, laptop, and 1080p recording layouts remain accessible and polished.

### 4. Codex entry point and release — conditional bonus plus final gate

After every P0 gate is green and both demo recordings exist:

- Add a minimal `polygraphml audit` CLI that reads `.polygraphml.yml`, submits a pinned public repository, waits through replay/resume, and emits JSON, Markdown, or GitHub job-summary output.
- Add a repo-local Codex skill that invokes this CLI and presents the resulting report URL and verdict. Use the existing single PolygraphML audit agent; the skill is an entry surface, not another audit agent.
- Defer GitHub Checks annotations, private repositories, and automatic blocking policies until after the hackathon.

Release sequence:

1. PR A: contracts, agent planner, probe dispatcher, evidence policy, provenance.
2. PR B: manifest-driven GitHub intake, bounded compute, benchmarks and eval harness.
3. PR C: SSE frontend, truthful labels, reports, repair bundle, demo polish.
4. Each PR targets `dev`, passes CI and GPT-5.6 Terra review.
5. Open a release PR from `dev` to `main`, rerun the complete gate, and tag `v0.2.0`.
6. Deploy the backend from the tagged container digest, then deploy the frontend from the same release SHA.
7. Verify frontend SHA, backend SHA, model provenance, DNS, TLS, CORS, SQS resume, DLQ, deletion, and the public GitHub benchmark.
8. Rotate the OpenAI key before final submission, update Secrets Manager and local `.env`, redeploy the worker, and repeat secret/history scanning.
9. Record the live demo and labeled fallback recording; verify final metadata and URLs.

## Test and Acceptance Plan

- **Unit/contract:** agent schemas, probe compatibility, target association, metric contract, finding policy, manifest validation, repair generation, provenance serialization, generated frontend types.
- **Property/security:** manifest paths, GitHub paths, archive rules, subprocess limits, idempotency, event ordering, payload sanitization, secret absence.
- **Integration:** public-repository import, API→SQS→worker, question/resume, duplicate delivery, timeout, SSE replay, polling fallback, report and repair storage.
- **Benchmark gates:** flagship confirmed and corrected; semantic proxy confirmed; hard negative cleared; two clean controls with zero false confirmations; raw case counts reported.
- **Live gate:** exactly one bounded live run each for flagship, semantic proxy, and hard negative, with at most five agent turns per run. Do not expand the sweep without explicit cost approval.
- **Release commands:** `make check`, `make test-e2e`, `make benchmarks`, `REF=<sha> make public-github-gate`, `make eval-live`, Terraform validation, full-history secret scan, deployed smoke, and exact build-SHA verification.

## Assumptions and Cut Lines

- `gpt-5.6-sol` remains the product investigator; `gpt-5.6-terra` remains the CI reviewer. OpenAI currently positions Sol as the flagship tier and Terra as the balanced lower-cost tier: [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/model-guidance?model=gpt-5.6-sol).
- One audit agent is sufficient; no swarm, handoffs, or debate architecture.
- `.skops`, CSV/Parquet, notebook inspection, and public GitHub remain the complete path. XGBoost, ONNX, private GitHub, arbitrary notebook execution, PDF, email, and additional audit families are cut before any P0 item.
- Raw chain-of-thought is never exposed; concise reasoning summaries remain labeled narration.
- The Codex CLI/skill is implemented only after the deployed P0 demo and fallback recording are complete.
- The release is not complete until the deployed frontend and backend expose the exact `v0.2.0` commit and the final submission package is verified.
