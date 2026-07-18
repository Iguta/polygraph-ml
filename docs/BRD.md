# Business Requirements Document — PolygraphML

**Version:** 1.0 · **Owner:** David · **Date:** July 18, 2026 · **Status:** Approved for build

## 1. Executive summary

PolygraphML is an adversarial validation tool for machine learning models. It detects data leakage — the most common silent failure in applied ML — and, uniquely, proves each finding by retraining the model without the tainted signal and demonstrating the performance collapse. The immediate business objective is to win the Developer Tools track of OpenAI Build Week 2026 (submission due July 21, 2026, 5:00 PM PT). The longer-term objective is to establish "ML QA" as a product category, with leakage detection as the wedge.

## 2. Business context and opportunity

The market has commoditized model *building*. SageMaker Autopilot, DataRobot, H2O AutoML, and PyCaret let anyone train competitive models in minutes. No corresponding investment has been made in model *validation*: leakage is caught today by senior-reviewer intuition, if at all. This is a structural gap, not a feature gap — the same asymmetry that created the SDET role when software development tooling outpaced software testing two decades ago.

The cost of the gap is documented. Kapoor & Narayanan (Princeton, *Patterns* 2023) surveyed 17 scientific fields and found leakage affecting 294+ published papers, with corrected results showing complex ML performing no better than logistic regression. Roberts et al. (*Nature Machine Intelligence* 2021) reviewed 300+ COVID-19 diagnostic ML models and found none clinically usable, with leakage-class dataset failures among the root causes. In industry, the same failure mode silently invalidates churn models (features populated after cancellation), predictive-maintenance models (failure-adjacent sensor readings bleeding into training windows), and credit models (post-outcome fields), with direct financial and safety consequences.

## 3. Business objectives

The primary objective is a winning hackathon submission: a working, polished, end-to-end product that scores highly on all four official judging criteria (Technological Implementation, Design, Potential Impact, Quality of the Idea). Secondary objectives are a public repository credible enough to serve as a portfolio anchor for David's data science consultancy, and validation of the "ML QA" positioning for potential post-hackathon development.

## 4. Target market and users

The primary user is the practicing data scientist or ML engineer who trains tabular models (churn, risk, maintenance, credit) and lacks tooling to verify them before deployment. Secondary users are team leads and reviewers who must sign off on model quality, and — via the stakeholder report — the non-technical decision-makers who consume model predictions. The hackathon judging panel (senior OpenAI staff, developer-heavy) is a deliberate proxy audience: they have all seen or shipped a leaked model.

## 5. Value proposition

For model builders, PolygraphML converts an invisible, reputation-destroying failure mode into a five-minute pre-deployment check with demonstrated (not asserted) findings. Against data-validation tools (Deepchecks, Great Expectations), the differentiation is semantic reasoning about feature meaning and temporal plausibility; against AutoML, it is the missing counterpart — AutoML gives you a model, PolygraphML tells you whether to trust it. The proof-by-ablation loop is the moat: no existing tool demonstrates its findings experimentally.

## 6. Success criteria

The submission is successful if it: runs end-to-end live (upload → interrogation → probes → proof → report) with no manual intervention; catches all planted leaks in the synthetic evaluation suite while clearing clean features (zero false accusations in the demo path); completes a full audit on the demo dataset in under 90 seconds; and is submitted on time with the required Codex Session ID, README documentation, and a sub-3-minute demo video. Winning first or second in Developer Tools is the outcome target; a top-quality submission meeting the criteria above is the controllable target.

## 7. Constraints and assumptions

The build window is approximately three days with a single builder. The project must use GPT-5.6 centrally and Codex visibly (hackathon rules). Scope is constrained to tabular datasets and scikit-learn/XGBoost-compatible models; no enterprise integrations, no accounts, no cloud training (SageMaker is roadmap only — local training keeps the demo fast and self-contained). Demo data is synthetic with planted, known leaks, avoiding any privacy or licensing exposure.

## 8. Risks to the business objective

The material risks are demo failure (mitigated by fast local retraining on small data and a rehearsed, recorded fallback), false accusations undermining credibility (mitigated by the synthetic ground-truth test suite and by showing the tool clearing clean features), and scope creep beyond the leakage wedge (mitigated by the explicit cut lines in the Build Plan). Competitive risk is low in-category: adjacent tools validate data, not models, and none proves findings by ablation.

## 9. Out of scope for this phase

Deep learning models, computer-vision and NLP datasets, CI/CD integration, multi-user collaboration, billing, SageMaker execution, and fairness or drift auditing are explicitly out of scope for the hackathon build. They appear in the roadmap section of the PRD as the broader "ML QA" vision.
