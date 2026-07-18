# Product Requirements Document — PolygraphML

**Version:** 1.0 · **Owner:** David · **Date:** July 18, 2026 · **Status:** Approved for build

## 1. Product statement

PolygraphML is the lie detector for machine learning models. A user uploads a tabular dataset (optionally with a trained model), names the target, and an agent interrogates the features for data leakage, probes the suspects statistically, proves confirmed leaks by retraining without them, and delivers a verdict dashboard plus a plain-English stakeholder report stating the model's honest expected performance.

## 2. Personas

**Priya, ML engineer at a mid-size SaaS company.** She inherited a churn model showing 97% validation accuracy that underperforms badly in production. She needs to find out why, and she needs evidence her manager will accept — not a hunch. PolygraphML gives her a demonstrated ablation experiment and a report she can forward.

**Marcus, data science consultant.** He reviews client models before deployment sign-off. Manual leakage review takes him half a day per model and depends entirely on his attention. He needs the skeptical-reviewer pass automated so his sign-off scales.

**The hackathon judge.** A senior developer who has personally been burned by a leaked model. They need to see, inside three minutes, a real product doing something no existing tool does.

## 3. Core user journey

The user lands on a single-screen dashboard, uploads a CSV, and selects the target column (and optionally a timestamp column). They press **Interrogate**. The agent's reasoning streams live: it profiles features, voices suspicions in plain language, runs probes, and marks findings as they land. For each confirmed suspect the user watches the proof: baseline metric, ablated retrain, and the delta rendered as a collapsing number. The session ends on a verdict panel — honest performance estimate, findings ranked by severity, each with mechanism and evidence — and a **Generate stakeholder report** action producing a shareable narrative document. The full flow is specified screen-by-screen in [PRODUCT_FLOW.md](PRODUCT_FLOW.md).

## 4. Functional requirements

**FR-1 Dataset intake.** Accept CSV upload up to 50 MB; infer column types; require target selection; accept optional time column and optional pickled sklearn/XGBoost model. Reject malformed files with actionable errors.

**FR-2 Semantic feature audit.** GPT-5.6 receives the schema, sample values, and summary statistics for every feature and returns, per feature, a structured leakage-risk assessment: risk level, suspected mechanism (target proxy, post-outcome population, temporal bleed, identifier, clean), and rationale in plain English. Output must conform to the Finding schema in [API_CONTRACT.md](API_CONTRACT.md).

**FR-3 Statistical probe suite.** Execute at minimum four probes: single-feature predictive power (per-feature AUC/importance vs. target), train/test contamination (duplicate and near-duplicate detection across splits), temporal ordering check (when a time column exists, verify no feature correlates with future-only information), and target-proxy correlation (features with implausibly high mutual information with the target). Each probe emits structured evidence attached to findings.

**FR-4 Proof by ablation.** For each confirmed suspect, retrain the model (or a standard baseline: logistic regression + XGBoost) without the suspect feature(s) on a proper split, and report baseline metric, ablated metric, and delta. Retraining must complete in seconds on demo-scale data. A finding is only labeled **Proven** when the ablation demonstrates material inflation.

**FR-5 Verdict and report.** Render a dashboard of findings ranked by severity with per-finding mechanism, confidence, and evidence, plus the honest performance estimate. Generate a stakeholder report (markdown, GPT-5.6-authored) translating the findings into business language. Email delivery is a stretch feature (FR-8).

**FR-6 Live narration.** Stream the agent's reasoning and probe progress to the UI via server-sent events so the interrogation is watchable, not a spinner.

**FR-7 Clean-feature clearance.** The audit must explicitly clear non-leaky features, and the demo must show it doing so. False accusations are treated as release-blocking defects.

**FR-8 (Stretch) Stakeholder email.** Send the generated report to a supplied address. **FR-9 (Stretch) Pickled-model intake** beyond the built-in baselines. **FR-10 (Stretch) Recurring audit config export.**

## 5. Non-functional requirements

Full audit on the demo dataset (~10k rows, ~20 features) completes in under 90 seconds; individual ablation retrains complete in under 10 seconds. The UI is a single-page application requiring zero onboarding. All GPT-5.6 outputs use structured outputs with schema validation; any non-conforming response is retried, never rendered raw. Uploaded data stays local to the server process; nothing is persisted beyond the session directory; no accounts, no tracking.

## 6. Scope boundaries

In scope: tabular CSV, binary and multiclass classification (regression if time allows), sklearn/XGBoost baselines, English-language reports, the churn demo scenario with a predictive-maintenance sample as secondary. Deliberately not built: deep learning support, image/text data, CI integration, accounts, SageMaker execution, fairness/drift/robustness audits (roadmap), multi-dataset projects.

## 7. Acceptance criteria for the hackathon build

The build is accepted when a fresh user can complete upload-to-report on the churn demo dataset without instruction in under three minutes; the synthetic evaluation suite (five datasets with planted leaks of known type, plus one fully clean dataset) yields 100% planted-leak detection and zero false Proven findings on the clean dataset; the streamed narration reads as a coherent interrogation; and the stakeholder report is accurate to the findings without hallucinated numbers (all figures injected from computed results, never model-generated).

## 8. Roadmap (post-hackathon vision)

Leakage is the wedge; the product is ML QA. The probe suite extends to robustness testing, segment-level failure analysis, drift monitoring, and fairness audits. Execution extends to SageMaker and CI pipelines ("Polygraph as a deployment gate"). The stakeholder report extends to scheduled model health digests. None of this is built now; all of it is why the wedge matters.
