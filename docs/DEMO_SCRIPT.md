# Demo Script — PolygraphML (3:00 max, target 2:50)

**Opening line, verbatim:**
> "PolygraphML is the lie detector for machine learning models — it interrogates your model, catches it cheating, and proves it by retraining without the leaked evidence."

## 0:00–0:20 — Hook and problem

On screen: a training notebook cell proudly printing `AUC: 0.982`. Voiceover: "This churn model just scored 98%. Would you ship it? Princeton researchers found data leakage invalidating research across seventeen fields, and an entire generation of COVID diagnostic models was rendered clinically useless by exactly this failure. AutoML made building models cheap — nobody built the QA layer. I spent two years as a software engineer in test. This is Polygraph."

## 0:20–1:50 — Live product workflow

0:20–0:35 — Upload the churn CSV, pick the target, one click on **Interrogate**. No configuration, no setup.

0:35–1:10 — The interrogation streams. Feature chips flip amber and green as the agent narrates its suspicions out loud; pause on the key line: *"`last_payment_status` contains values like 'chargeback' that post-date cancellation — flagging as a post-outcome leak."* Point out a legitimate-looking feature getting **cleared** green: "Notice it doesn't cry wolf — `monthly_spend` is genuinely predictive, and Polygraph clears it."

1:10–1:35 — **The wow moment.** The proof card: baseline **0.982** on screen, "retraining without the leaked feature…", and the metric collapses live to **0.714**. Beat of silence. "That's not an opinion. That's an experiment. The model was cheating, and Polygraph just proved it."

1:35–1:50 — The verdict panel and one scroll of the stakeholder report: "…and it hands your VP the honest number in plain English."

## 1:50–2:30 — Technical and AI differentiation

Split screen: architecture diagram + a snippet of the agent session log. "The core is a division of labor: GPT-5.6 reasons — about what each feature *means* and *when it could have been known*, which no statistical test can do — while deterministic Python computes every number. GPT-5.6 never invents a metric; it interprets proofs. And Codex built this end to end: the probe harness, the retraining sandbox, and a synthetic test suite of datasets with *planted* leaks — so Polygraph is itself tested against ground truth. The session ID is in the README."

## 2:30–3:00 — Result, impact, closing

"Deepchecks validates your data. AutoML builds your model. Nothing validates what the model *learned* — until now. Churn, credit, predictive maintenance, medicine: everywhere accuracy matters, leakage is shipping silently. Polygraph is the adversarial QA engineer for machine learning — leakage today; robustness, drift, and fairness next. Two years breaking software taught me one thing: everything ships with bugs until something is paid to find them. PolygraphML." End card: repo URL + tagline.

## Production notes

Record against localhost with the synthetic churn dataset (planted leaks: `last_payment_status` post-outcome, `days_to_renewal_notice` temporal; clean control: `monthly_spend`). Rehearse until the live path is boring; keep one fully recorded clean take as fallback. The proof-card collapse must land between 1:10 and 1:35 — if audit latency drifts, trim narration in 0:35–1:10, never the proof. Mute notifications, 1080p, cursor highlighting on, no dead air over 2 seconds.

## The one-slide summary (if a pitch slide is allowed)

Claimed 0.982 → Honest 0.714, with the strapline: **"AutoML gives you a model. Polygraph tells you whether to trust it."**
