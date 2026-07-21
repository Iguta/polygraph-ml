# Business Requirements Document — PolygraphML

**Version:** 1.2 · **Owner:** David · **Date:** July 21, 2026 · **Status:** v0.2 release candidate

## 1. Executive summary

PolygraphML is an adversarial validation product for machine learning systems. It evaluates the trained model, dataset, and training/evaluation pipeline together, preferably from the original Jupyter notebook or GitHub repository. It reproduces the reported metric, investigates scenario-dependent leakage and evaluation defects, applies a defensible correction, and reports the measured impact with a replayable decision trace.

The immediate objective is a polished, deployed OpenAI Build Week 2026 submission in the Developer Tools track. The longer-term objective is to establish **ML QA** as a product category, with evidence-backed leakage and evaluation auditing as the entry point.

## 2. Business problem

Model-building tools optimize for training speed and headline metrics. Trust still depends on manual review of feature availability, split design, preprocessing, evaluation code, and deployment context. This creates predictable failures:

- post-outcome or future information is available during training but not at prediction time;
- the same entity or near-duplicate rows appear across train and test;
- preprocessing is fit before the split;
- the reported metric cannot be reproduced from the submitted artifacts;
- a statistically suspicious feature is accused without understanding the real decision scenario.

Auditing only a dataset is insufficient. Leakage is a property of the relationship among data, code, model, evaluation protocol, and intended use. A feature can be legitimate in one scenario and leakage in another.

## 3. Value proposition

For data scientists and ML reviewers, PolygraphML turns a slow, intuition-heavy review into an inspectable experiment. It does not stop at “this column looks suspicious.” It shows:

- what the submitted system claims;
- whether that claim can be reproduced;
- which assumption or mechanism is under test;
- what deterministic probe was run;
- what evidence confirms, clears, or leaves the issue inconclusive;
- how performance changes under a corrected evaluation.

The differentiator is not generic data profiling. It is **scenario-aware investigation plus reproducible proof**.

## 4. Target users

**Primary:** practicing data scientists and ML engineers auditing tabular classification systems before deployment.

**Secondary:** technical reviewers, consultants, model-risk teams, and engineering leads who need review evidence they can challenge and share.

**Hackathon audience:** technically sophisticated judges who should understand the problem and witness the full evidence loop in under three minutes.

## 5. Business objectives

1. Deliver a reliable, beautiful, end-to-end hackathon product deployed on Vercel and AWS.
2. Make GPT-5.6 central to semantic reasoning and investigation planning, while keeping numerical claims deterministic.
3. Demonstrate a public, reproducible validation case in addition to synthetic planted-leak tests.
4. Produce a repository and architecture credible as the foundation of a post-hackathon ML QA product.
5. Preserve an extensible adapter and benchmark model so initial formats and domains do not become permanent limits.

## 6. Success criteria

The hackathon release succeeds when:

- a user can submit either a public GitHub repository or an artifact bundle containing the model, dataset, and optional notebook;
- the system captures the prediction scenario and asks a follow-up question when a material assumption is missing;
- an audit survives browser refresh because it is queued through SQS and persisted server-side;
- the system displays reported, reproduced, and corrected metrics without allowing the LLM to invent any number;
- every confirmed finding links to deterministic evidence and a rerunnable correction;
- a supported literal-feature notebook produces a hash-addressed repair bundle, while ambiguous code returns an explicit unavailable result;
- a clean-control benchmark produces zero false confirmed findings;
- fixture quality is reported with raw case counts and uncertainty, and the bounded live gate is limited to three predeclared model calls;
- at least one planted-leak benchmark and one curated public benchmark complete end to end;
- the React experience is polished, intuitive, responsive, and demo-ready;
- the deployed demo path completes within the agreed performance budget and has a deterministic recorded fallback;
- the repository includes required Codex usage documentation and an honest implementation log.

## 7. Product and technical constraints

- OpenAI is the initial model provider; `gpt-5.6-sol` is the primary audit model through the Responses API and OpenAI Agents SDK.
- One audit agent with typed tools is the default. Multi-agent complexity requires evaluation evidence before adoption.
- The OpenAI API key is server-side only and stored in AWS Secrets Manager; it must never enter browser code, SQS messages, logs, or source control.
- The hackathon release statically inspects repositories and notebooks and never executes arbitrary submitted source. Any future execution requires a separate disposable, no-secret, resource-limited task.
- Remote pickle, joblib, and cloudpickle artifacts are rejected. Safe adapters are introduced incrementally.
- Initial deep support is tabular classification with scikit-learn/skops. XGBoost and ONNX are recognized as limited adapter paths without narrowing the eventual product boundary.
- Public benchmark use requires verified provenance, license, expected finding, and reproducible setup.

## 8. Material risks and mitigations

| Risk | Business impact | Mitigation |
|---|---|---|
| False accusation | Destroys trust in the product | Scenario questions, confirmation criteria, clean controls, and an `inconclusive` state |
| Ablation mistaken for proof | Overstates what the evidence supports | Require mechanism evidence plus measured inflation; describe ablation as impact evidence |
| Untrusted code execution | Security compromise | Do not execute submitted source in P0; require a separate no-secret sandbox before enabling it |
| API key or cost exposure | Financial/security loss | Secrets Manager, backend-only calls, rate limits, quotas, redacted logs |
| Demo waits or fails | Weak judging experience | SQS durability, saved demo fixture, polling fallback, rehearsed recorded run |
| Public case is irreproducible or improperly licensed | Credibility/legal risk | Benchmark admission checklist and synthetic fallback |
| Scope expansion | Core loop remains incomplete | Phased DoD and explicit hackathon cut lines |

## 9. Scope boundaries

The hackathon release is not a universal validator for every ML framework. It prioritizes one excellent vertical slice: a tabular model plus its dataset and notebook/repository, audited end to end. Dataset-only preflight may exist as a secondary mode, but it is not the product claim.

Deep learning, computer vision, NLP, private GitHub authentication, arbitrary dependency execution, continuous monitoring, fairness, drift, and enterprise governance belong to the roadmap. The roadmap is open-ended; the initial adapter list is a starting point, not the definition of PolygraphML.
