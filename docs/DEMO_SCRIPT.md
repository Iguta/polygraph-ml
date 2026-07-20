# Demo Script — PolygraphML

**Maximum:** 3:00 · **Target:** 2:45–2:50 · **Status:** deployed path and live-agent evidence verified; final polished recording still required

## Opening line

> “PolygraphML is the evidence-backed lie detector for machine learning systems. It audits the model, data, and notebook together—and shows the score the model actually earned.”

## 0:00–0:20 — The problem

Show the campaign benchmark notebook reporting ROC AUC `1.000`.

“This model reports AUC 1.000. But a metric is only as trustworthy as the data, split, preprocessing, and moment of prediction behind it. Auditing the CSV alone cannot answer that. PolygraphML reconstructs the whole claim.”

## 0:20–0:48 — Submit real evidence

Open **Try a benchmark** or paste the pinned public GitHub repository. Show the artifact map detecting:

- the notebook and metric cell;
- the evaluation dataset;
- the safe model artifact;
- the target and split logic;
- the exact source commit.

Confirm the scenario: predictions select customers before a campaign call begins.

“The scenario matters. The same feature may be legitimate after a call and leakage before it.”

## 0:48–1:35 — Watch the Decision Trace

Start the audit. Briefly point out that it is queued durably through SQS and survives refresh.

The trace shows:

1. **Reported metric:** extracted from the notebook.
2. **Reproduction:** the submitted evaluation reruns within tolerance.
3. **Hypothesis:** `call_duration` may be unavailable at decision time.
4. **Falsification condition:** the concern disappears if prediction occurs after the completed call.

Let PolygraphML ask:

> “Is `call_duration` available when customers are selected, or only after the call finishes?”

Answer **after the call**. Show the answer becoming part of the audit evidence, followed by the deterministic availability and ablation/correction probes.

“This is not hidden chain-of-thought. It is an audit trail: assumptions, hypotheses, tests, evidence, and corrections.”

## 1:35–1:58 — The proof moment

Show the captured fixture comparison:

```text
Reported   1.000
Reproduced 1.000
Corrected  0.863
```

“The headline score was real under the submitted evaluation, but invalid for the stated decision moment. PolygraphML removed the unavailable signal, repaired the evaluation, and measured the impact. Feature reliance alone is not called leakage—the scenario and code evidence complete the case.”

Expand the finding so the judge sees source references and **What would change this conclusion?** Briefly show one legitimate feature or clean check being cleared.

## 1:58–2:30 — Technical differentiation

Show the architecture and a compact trace schema.

“OpenAI GPT-5.6 Sol is the investigator. Through the OpenAI Agents SDK it forms falsifiable hypotheses, selects typed tools, and asks the question a static checker cannot. Deterministic Python computes every number. SQS makes the audit durable, DynamoDB stores the trace, and untrusted artifacts never execute in the API process. The React experience is deployed on Vercel; the backend runs on AWS.”

Show the public UCI COVID-19 surveillance clean-control result: zero confirmed findings and zero reproduction error. State clearly that it is a 14-row teaching dataset, not clinical validation.

“The auditor is itself evaluated: planted leaks, clean controls, and pinned public model-plus-data cases with expectations declared in advance.”

## 2:30–2:50 — Close

Show the stakeholder report and end card.

“AutoML helps you build a model. PolygraphML tells you whether to trust what it learned. Leakage is the first audit family; robustness, drift, fairness, and continuous deployment gates come next. PolygraphML—the QA layer for machine learning.”

## Recording rules

- Use the checked-in `benchmark-results/latest.json` values; rerun the gate immediately before recording.
- Display a live badge only during an actual live run; a fixture fallback must be labeled.
- Record against `https://polygraphml.davidiguta.com` and keep a complete local recording as contingency.
- Hide browser developer tools, secrets, presigned URLs, account identifiers, and AWS console details.
- Keep the primary proof card on screen long enough to read at 1080p.
- Do not make a clinical claim in the COVID case study. If that benchmark is not fully reproducible and licensed before recording, leave it in the roadmap/benchmark gallery rather than the main demo.

## One-slide summary

**Reported → Reproduced → Corrected**, with the strapline:

> “A model score is a claim. PolygraphML audits the evidence.”
