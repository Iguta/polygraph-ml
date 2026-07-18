# Product Flow — PolygraphML

**Version:** 1.0 · One screen, five states. The product is a single-page dashboard that transforms in place — the user never navigates.

## State 1 — Landing / Intake

The user sees the product promise ("The lie detector for machine learning models"), a drop zone, and a sample-dataset shortcut ("Try it on a leaky churn model") that pre-loads the demo CSV. On upload, a compact schema table appears with dropdowns for **Target column** and optional **Time column**, plus an optional one-line business-context field ("This is a SaaS churn dataset"). A single primary button: **Interrogate**. Design intent: zero onboarding — a first-time judge must reach the button in under ten seconds.

## State 2 — Interrogation (live)

The centerpiece. The screen splits: the left rail lists every feature as a chip (neutral gray), and the main panel streams the agent's narration as a live transcript. As the semantic audit lands, chips recolor — amber for suspects, green for cleared — and narration entries voice the reasoning: *"`last_payment_status` contains values like 'chargeback' that typically post-date cancellation. Flagging as a suspected post-outcome leak."* Probe activity renders inline with mini progress bars per probe. Emotional target: the user is watching an expert think, not waiting on a spinner.

## State 3 — Proof (the moment)

When a suspect enters ablation, the main panel foregrounds a proof card: the baseline metric displayed large (e.g., **AUC 0.982**), a "retraining without `last_payment_status`…" progress state lasting a few visible seconds, then the ablated metric animating downward to **0.714** with the delta stamped in red. The suspect's chip turns red (**Proven**). This collapse animation is the product's wow moment and the demo's centerpiece; it must be smooth, legible at a glance, and honest (numbers come straight from the `Proof` object).

## State 4 — Verdict

The transcript collapses into a summary header: claimed performance vs. honest performance side-by-side, a severity-ranked findings table (feature, type, mechanism in one sentence, evidence link, status), and cleared features listed affirmatively ("6 features interrogated and cleared"). Each finding expands to its full rationale and evidence. Primary action: **Generate stakeholder report**; secondary: **Download findings (JSON)**, **Run again**.

## State 5 — Report

A rendered markdown report in an elegant reading layout: an executive summary in business language ("The model's reported 98% is not real…"), the honest performance estimate, per-finding explanations translated for non-technical readers, and recommended next steps (remove features X and Y, retrain, re-audit). Actions: copy, download `.md`, and — if the stretch lands — send by email. The report ends with the audit's session ID and timestamp for traceability.

## Error and edge flows

A malformed CSV returns the user to State 1 with a specific message ("Column count varies at row 1,204"). A probe timeout leaves the finding visible as *Suspected — probe incomplete* rather than blocking the verdict. A model-output validation failure downgrades gracefully: statistical findings render with a notice that semantic rationale is unavailable. A fully clean dataset is a first-class flow, not an empty state: the verdict celebrates it ("No leakage proven. Claimed performance stands.") — this is also a demo beat, shown briefly to establish that Polygraph doesn't cry wolf.

## Flow ↔ demo mapping

State 1 covers demo 0:20–0:35, State 2 covers 0:35–1:10, State 3 covers 1:10–1:35 (the wow moment), State 4–5 cover 1:35–1:50, leaving the architecture reveal and closing per [DEMO_SCRIPT.md](DEMO_SCRIPT.md). Every state must therefore be individually screenshot-worthy — the video will linger on each for only seconds.
