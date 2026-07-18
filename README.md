# PolygraphML

**The lie detector for machine learning models.**

> Your model says it's 98% accurate. PolygraphML interrogates it, catches it cheating, and proves it — by retraining without the leaked evidence and showing you the truth.

---

## Why this exists

AutoML made building models cheap. Nobody built the QA layer that cheapness demands.

Every tool in the market races to make training easier. The faster models get built, the more unvalidated models ship. Data leakage — features that secretly encode the target, contamination between train and test sets, future information bleeding into training windows — is the most common silent failure in applied machine learning. The model looks brilliant in validation and collapses in production.

The evidence is damning. Princeton researchers found data leakage across **17 scientific fields, affecting 294+ published papers**, producing wildly overoptimistic conclusions — and when corrected, complex ML models performed no better than decades-old logistic regression (Kapoor & Narayanan, *Patterns*, 2023). A Cambridge-led systematic review of **300+ COVID-19 diagnostic ML models found that not one was suitable for clinical use**, with leakage-class failures — like training sets that used children's images for "non-COVID" cases — among the root causes (Roberts et al., *Nature Machine Intelligence*, 2021).

Twenty years ago, software development tooling exploded, and the SDET role had to be invented to keep quality in step with velocity. Machine learning is at that exact moment now. PolygraphML is the adversarial QA engineer for ML models.

## What it does

Point PolygraphML at a trained model and its dataset. An agent powered by **GPT-5.6** then does what a skeptical senior reviewer would do — at machine speed:

1. **Interrogates** — profiles every feature and reasons *semantically* about leakage risk. Statistical checks can flag "suspiciously predictive"; only a language model can reason that `days_since_last_ticket_closed` is probably populated *after* churn happens.
2. **Probes** — runs targeted checks: single-feature predictive power, train/test contamination, duplicate detection, temporal ordering violations.
3. **Proves** — for each suspect, retrains the model *without* the tainted signal and quantifies the collapse: *"98.2% → 71.4% without `last_payment_status`. This feature is leaking the target."*
4. **Reports** — produces a verdict dashboard and a plain-English stakeholder report: your model's honest expected production performance, and exactly why.

Not just detection. **Proof by ablation.** The finding isn't an opinion — it's a demonstrated experiment you can rerun.

## Why GPT-5.6 is necessary, not decorative

The core of PolygraphML is semantic reasoning about *what a feature means* and *when it could have been known*. That is a language-understanding problem no statistical test solves. GPT-5.6 designs the probe plan per-dataset, reasons about temporal and causal plausibility of each feature, interprets probe results in context, and writes the stakeholder narrative. Structured outputs guarantee every finding conforms to an auditable schema.

## How Codex built it

Codex was the build agent for this project end-to-end: it scaffolded the FastAPI service and React dashboard, implemented the agent orchestration and probe harness, built the sandboxed retraining loop, and — critically — authored a **test suite of synthetic leaky datasets with known, planted leaks**, proving PolygraphML catches what it claims to catch (and clears clean features). See [`docs/CODEX_USAGE.md`](docs/CODEX_USAGE.md) for the session log narrative and Session ID.

## Project documents

| Document | Purpose |
|---|---|
| [BRD](docs/BRD.md) | Business case, market context, success criteria |
| [PRD](docs/PRD.md) | Product requirements, personas, scope, MVP definition |
| [TDD](docs/TDD.md) | Technical design — components, data flow, decisions |
| [Solution Architecture](docs/SOLUTION_ARCHITECTURE.md) | System architecture, stack, deployment |
| [API Contract](docs/API_CONTRACT.md) | REST endpoints, schemas, streaming events |
| [Product Flow](docs/PRODUCT_FLOW.md) | End-to-end user journey and screen states |
| [Demo Script](docs/DEMO_SCRIPT.md) | The 3-minute hackathon demo, timestamped |
| [Build Plan](docs/BUILD_PLAN.md) | Day 1–3 execution plan and cut lines |
| [Codex Usage](docs/CODEX_USAGE.md) | How Codex was used (hackathon requirement) |

## Quickstart (target state)

```bash
git clone https://github.com/davidigutaorg/polygraph-ml.git
cd polygraph-ml
make dev            # starts API (FastAPI) + dashboard (Vite)
# open http://localhost:5173, upload a CSV, pick a target, hit Interrogate
```

## Status

🚧 OpenAI Build Week 2026 — under active construction. Track: **Developer Tools**.

## License

MIT — see [LICENSE](LICENSE).

---

*Built by David — two years breaking software as an SDET, now breaking models before production does.*
