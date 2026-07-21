# Product Roadmap — PolygraphML

**Version:** 1.1 · **Owner:** David · **Date:** July 21, 2026

## Roadmap principle

PolygraphML starts with one narrow, high-trust workflow and expands through adapters and audit families. The initial list of model formats and public datasets is a launch point, not a permanent ceiling. New capability is admitted only when it preserves the core evidence contract: scenario, hypothesis, deterministic probe, provenance, correction, and measured result.

## Horizon 0 — Hackathon vertical slice

**Goal:** prove the category with a polished, deployed, end-to-end audit.

Product scope:

- public GitHub repository and upload-bundle intake;
- tabular binary classification;
- `.skops` primary model path, XGBoost JSON/UBJ if the primary path is stable;
- CSV/Parquet and Jupyter notebook inspection;
- one GPT-5.6 Sol audit agent with follow-up questions;
- reported/reproduced/corrected metrics;
- post-outcome/availability, semantic target-proxy, metric-contract, exact/group contamination, preprocessing-order, held-out association, and ablation/correction probes; temporal backtesting and near-duplicate similarity remain explicit limitations;
- strict `.polygraphml.yml` repository manifests and bounded, non-sandboxed `.skops` compute;
- Decision Trace, technical/executive Markdown reports, and a deterministic repair archive;
- React/Vercel frontend and AWS/SQS backend;
- synthetic planted-leak suite, clean control, and one pinned public benchmark.

Exit evidence is defined in [IMPLEMENTATION_PHASES.md](IMPLEMENTATION_PHASES.md).

## Horizon 1 — Credible beta (0–3 months)

**Goal:** broaden practical usefulness without sacrificing reproducibility.

- private GitHub integration with least-privilege OAuth;
- richer repository manifests and dependency-lock recognition;
- broader scikit-learn estimator coverage, XGBoost, LightGBM, CatBoost, ONNX, and MLflow model bundles;
- regression and multiclass evaluation;
- robust grouped, nested, and time-series cross-validation reconstruction;
- broader reproducibility bundles for dynamic pipelines beyond the shipped literal-feature patch boundary;
- team projects, durable history, shareable review links, comments, and approval states;
- benchmark dashboard showing quality, latency, and cost by release;
- a broader curated public case library; the initial licensed UCI COVID-19 surveillance clean control is shipped, while any clinical-scale COVID reproduction requires separate provenance and claim validation.

## Horizon 2 — ML QA platform (3–6 months)

**Goal:** move from one-time leakage review to pre-deployment model quality gates.

New audit families:

- robustness and perturbation testing;
- subgroup and segment failure analysis;
- calibration and threshold-policy review;
- fairness analysis with explicit policy/context inputs;
- uncertainty and abstention behavior;
- data/feature drift baselines;
- train/serve skew and preprocessing equivalence.

Workflow expansion:

- GitHub Checks and pull-request annotations;
- CLI and CI exit-code policy;
- artifact registries and experiment trackers;
- scheduled and webhook-triggered audits;
- issue tracker/export integrations;
- organization policy packs and signed audit reports.

## Horizon 3 — Continuous assurance (6–12 months)

**Goal:** become the system of record for model trust across the lifecycle.

- production monitoring connected to pre-deployment audit assumptions;
- drift-triggered re-audit and corrected-model comparison;
- cross-version regression testing for models and feature pipelines;
- governed evidence retention, access controls, audit approvals, and compliance exports;
- distributed execution through managed training backends;
- support for deep-learning, vision, NLP, recommendation, forecasting, and foundation-model evaluation through domain-specific adapters;
- multi-agent specialist reviews only where benchmarked against the single-agent baseline;
- provider abstraction and approved model routing where customer requirements justify it.

## Benchmark roadmap

The registry grows by **case quality**, not by collecting famous datasets.

Every admitted case needs:

- immutable source and artifact hashes;
- license and redistribution status;
- model plus dataset plus notebook/pipeline evidence;
- scenario and intended decision moment;
- expected findings declared before execution;
- clean or negative checks, not only planted failures;
- reproduction instructions and tolerance;
- known limitations and prohibited claims.

Planned benchmark layers:

1. micro synthetic cases for one mechanism at a time;
2. multi-mechanism synthetic systems;
3. clean synthetic controls;
4. public tabular repository/model cases;
5. domain case studies such as health/COVID, credit, maintenance, churn, and marketing;
6. community-contributed cases accepted through review and continuous regression tests.

## Explicitly deferred decisions

- pricing and billing model;
- regulated-industry certification claims;
- customer-selected model providers;
- executing arbitrary third-party dependency graphs;
- a multi-agent architecture;
- claiming that an audit guarantees future production performance.

These remain open until user research, benchmark evidence, security design, and operating cost justify them.
