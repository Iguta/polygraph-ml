# PolygraphML

**The evidence-backed lie detector for machine learning systems.**

> A model can score brilliantly for the wrong reason. PolygraphML audits the model, dataset, and training pipeline together; reproduces the claimed result; tests leakage hypotheses; and shows the corrected result with a replayable evidence trail.

## Why this exists

Model building has become dramatically easier, but model validation still depends on careful senior review. Data leakage, contaminated splits, post-outcome features, inconsistent preprocessing, and evaluation mistakes can make a model look production-ready when it is not.

PolygraphML is an adversarial QA engineer for tabular ML. It does not merely scan a dataset or offer an LLM opinion. It reconstructs what was built, asks when and how predictions will be used, runs deterministic probes, and distinguishes three numbers:

1. **Reported** — the metric claimed by the notebook, repository, or user.
2. **Reproduced** — the metric obtained by rerunning the submitted evaluation.
3. **Corrected** — the metric obtained after repairing confirmed evaluation or leakage defects.

## What a user submits

A complete audit needs the model and the evidence required to evaluate it:

- A public GitHub repository, preferably containing the training notebook or pipeline code.
- Or an upload bundle containing a dataset, model artifact, optional Jupyter notebook, and manifest.
- The prediction scenario: target, decision point, prediction horizon, entity/row meaning, and intended metric.

The initial artifact adapters are deliberately safe and extensible:

- Jupyter notebooks (`.ipynb`) and Python pipeline code.
- Tabular datasets (`.csv` and `.parquet`).
- scikit-learn artifacts serialized with `.skops`.
- XGBoost `.json` or `.ubj` files recognized as a limited adapter path.
- ONNX files recognized and labeled limited; inference equivalence is P1.

Arbitrary JSON is not treated as a model format, and remotely supplied pickle, joblib, or cloudpickle files are rejected because loading them can execute code. The current GitHub path statically imports supported evidence files at a pinned commit; it does not execute arbitrary repository dependency graphs.

## How the audit works

1. **Reconstruct** — map the dataset, model, notebook, split logic, preprocessing, metric, and claimed result.
2. **Clarify** — ask targeted follow-up questions when the prediction scenario or artifact mapping is ambiguous.
3. **Reproduce** — run the submitted evaluation in an isolated, resource-limited environment.
4. **Interrogate** — GPT-5.6 Sol forms explicit, falsifiable hypotheses about feature availability, temporal ordering, split contamination, target proxies, and evaluation design.
5. **Probe** — deterministic Python tools test those hypotheses.
6. **Correct** — repair confirmed defects, retrain or reevaluate, and quantify the impact.
7. **Report** — present reported, reproduced, and corrected performance plus a replayable decision trace.

The operating principle is: **the model reasons; code computes; evidence decides.**

## Transparency without pretending to expose private thoughts

PolygraphML does not claim to reveal raw chain-of-thought. Its user-visible **Decision Trace** records the information needed to understand and challenge an audit:

- assumptions and user answers;
- hypotheses and concise rationale summaries;
- the probe selected and what could falsify the hypothesis;
- tool inputs, outputs, computed metrics, and evidence references;
- corrections applied and status changes;
- model identifier, prompt/schema version, artifact hashes, timestamps, and errors.

This trace is the product's transparency contract. OpenAI reasoning summaries may improve the narration, but a finding is never confirmed by narration alone.

## AI and application architecture

- **Model provider:** OpenAI.
- **Primary model:** `gpt-5.6-sol` through the Responses API.
- **Agent runtime:** OpenAI Agents SDK for Python, with the official `openai` SDK available for lower-level calls.
- **Agent topology:** one audit agent with typed tools and human-in-the-loop questions for the initial release. Additional agents are introduced only when evaluation shows a concrete need.
- **Frontend:** polished React application deployed to Vercel.
- **Backend:** FastAPI services and isolated audit workers on AWS.
- **Job execution:** Amazon SQS queues durable audit jobs; payloads contain references, never uploaded files or API keys.
- **Storage:** S3 for artifacts, DynamoDB for audit state and decision-trace events, Secrets Manager for the server-side OpenAI key.

## Validation strategy

PolygraphML is validated against both manufactured ground truth and public cases:

- synthetic datasets with planted leakage and clean controls;
- public datasets paired with reproducible notebooks/models and scenario-specific expected findings;
- a curated public COVID-19 case study after its model, dataset license, provenance, and reproducibility are verified;
- an expanding benchmark registry rather than a fixed list of supported domains.

Benchmark expectations are declared before the audit is run. A clean control producing a false confirmed finding is release-blocking.

## Project documents

| Document | Purpose |
|---|---|
| [Repository instructions](AGENTS.md) | Durable implementation, evidence, security, and verification rules for Codex |
| [BRD](docs/BRD.md) | Business case, success criteria, constraints, and risks |
| [PRD](docs/PRD.md) | Product requirements, personas, MVP, and acceptance criteria |
| [TDD](docs/TDD.md) | Audit engine, data model, security, and testing design |
| [Solution Architecture](docs/SOLUTION_ARCHITECTURE.md) | AWS/Vercel architecture and deployment topology |
| [API Contract](docs/API_CONTRACT.md) | Submission, audit, question, event, and report contracts |
| [Product Flow](docs/PRODUCT_FLOW.md) | End-to-end React experience and screen states |
| [Implementation Phases](docs/IMPLEMENTATION_PHASES.md) | Ordered implementation plan with Definition-of-Done checklists |
| [Roadmap](docs/ROADMAP.md) | Hackathon scope and post-hackathon expansion |
| [Benchmarks](docs/BENCHMARKS.md) | Registry cases, captured results, provenance, and release gate |
| [Deployment](docs/DEPLOYMENT.md) | AWS/Vercel deployment and production verification runbook |
| [Demo Script](docs/DEMO_SCRIPT.md) | Target hackathon demo narrative |
| [Build Plan](docs/BUILD_PLAN.md) | Critical path and cut lines |
| [Codex Usage](docs/CODEX_USAGE.md) | Honest implementation-session log |

## Quickstart

Prerequisites are Python 3.14, `uv`, Node.js 22, and npm. The default path is deterministic fixture mode and does not require an API key.

```bash
git clone https://github.com/davidigutaorg/polygraph-ml.git
cd polygraph-ml
make install
make dev
```

Open `http://localhost:5173`. The API runs at `http://localhost:8000`, and the worker consumes the local durable queue. Run the full local gates with:

```bash
make check
make test-e2e
uv run polygraphml-benchmarks --output benchmark-results/latest.json
make calibrate-queue
```

For live-agent development, place `OPENAI_API_KEY` in the ignored `.env` and set `POLYGRAPHML_AGENT_MODE=live`. Never commit or paste a key into source or logs. AWS injects the production key into the worker from Secrets Manager; Vercel and the API task do not receive it.

Once configured, `make live-smoke` runs one real model-system audit and writes a metadata-only, sanitized trace for review. It fails rather than silently accepting fixture degradation.

To exercise the deployed API and worker boundary with a disposable live benchmark audit, run:

```bash
API_URL=https://api.polygraphml.davidiguta.com make deployed-smoke
```

This verifies queue processing, question/resume, event replay, and deletion, then saves metadata-only evidence to `benchmark-results/deployed-smoke.json`.

## Status

OpenAI Build Week 2026 — deployed React frontend and AWS API/worker vertical slice with sanitized local and public-path live-agent evidence. Production resilience drills, final Git review, and submission packaging remain open. Track: **Developer Tools**.

## License

MIT — see [LICENSE](LICENSE).

---

*Built by David — two years breaking software as an SDET, now breaking models before production does.*
