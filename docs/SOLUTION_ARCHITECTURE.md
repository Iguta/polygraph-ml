# Solution Architecture — PolygraphML

**Version:** 1.0 · **Owner:** David · **Date:** July 18, 2026

## 1. Architecture at a glance

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (React SPA)                       │
│   Upload · Live interrogation view · Verdict dashboard · Report  │
└───────────────▲──────────────────────────────┬───────────────────┘
                │  SSE (audit events)          │  REST (JSON)
┌───────────────┴──────────────────────────────▼───────────────────┐
│                     FastAPI backend (Python 3.12)                │
│                                                                  │
│  ┌────────────┐   ┌──────────────────────────────────────────┐   │
│  │  Intake    │   │            Audit Orchestrator            │   │
│  │  service   │──▶│         (OpenAI Agents SDK loop)         │   │
│  └────────────┘   │                                          │   │
│                   │  ┌────────────┐  ┌───────────────────┐   │   │
│                   │  │ Semantic   │  │  Probe harness    │   │   │
│                   │  │ auditor    │  │  (deterministic)  │   │   │
│                   │  │ GPT-5.6 ───┼─▶│  power · contam · │   │   │
│                   │  └────────────┘  │  temporal · proxy │   │   │
│                   │                  └─────────┬─────────┘   │   │
│                   │  ┌────────────┐  ┌─────────▼─────────┐   │   │
│                   │  │ Verdict    │◀─│  Ablation prover  │   │   │
│                   │  │ composer   │  │  (sklearn/XGBoost │   │   │
│                   │  │ GPT-5.6    │  │   retrain loop)   │   │   │
│                   │  └────────────┘  └───────────────────┘   │   │
│                   └──────────────────────────────────────────┘   │
│        Session store: per-audit JSON on local disk               │
└───────────────────────────────┬──────────────────────────────────┘
                                │ HTTPS
                        ┌───────▼────────┐
                        │  OpenAI API    │
                        │  GPT-5.6       │
                        │  sol/terra/luna│
                        └────────────────┘
```

## 2. Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Python 3.12, FastAPI, uvicorn | Async SSE support; David's home turf; fastest path |
| Agent orchestration | OpenAI Agents SDK | Typed tools, session logging, hackathon-native |
| LLM | GPT-5.6 — `sol` for semantic audit, `terra`/`luna` for narration & report | Depth where it matters, cost/latency control elsewhere |
| ML engine | pandas, scikit-learn, XGBoost | Second-fast retrains on demo-scale data |
| Frontend | React 18 + Vite + Tailwind | Fast build, polished dashboard, Playwright-testable |
| Streaming | Server-sent events | Simpler than websockets; one-directional fits the flow |
| Persistence | Per-session JSON directory | Zero-ops; no DB in a 3-day build |
| Testing | pytest + synthetic leak suite; Playwright smoke | Ground-truth verification; demo-path insurance |
| Packaging | Makefile + `uv` (Python) + npm | `make dev` runs everything |

## 3. Model-tier strategy

The semantic audit — reasoning about what each feature means and when it could be known — is the hard, singular call and runs on `gpt-5.6-sol`. Interrogation narration (many small, latency-sensitive messages) runs on `luna`. The stakeholder report (one medium-depth generation with all figures templated in) runs on `terra`. This keeps the audit under the 90-second budget and per-audit cost in cents.

## 4. Data flow and trust boundaries

Uploaded data never leaves the backend host except as *summarized profiles* sent to the OpenAI API (schema, statistics, small sample values) — full datasets are not transmitted. All model outputs pass schema validation before entering application state. Computed metrics flow one direction: Python → prompt context → narrative; the reverse path (model-asserted numbers) is structurally impossible because the renderer only reads metric fields from `Proof` objects.

## 5. Deployment

Local-first for the hackathon: single host running `make dev` (uvicorn on :8000, Vite on :5173). The demo video is recorded against localhost, which the rules permit; a single-container Dockerfile (`docker compose up`) is included so judges can run it in one command. No cloud deployment is required or attempted in the build window — reliability of the local demo outranks a hosted URL. If time allows on Day 3, a Fly.io deploy of the container is the only acceptable stretch.

## 6. Security and privacy posture

No accounts, no telemetry, no persistence beyond the session directory, demo data fully synthetic. The only external call is to the OpenAI API. Upload size caps and dtype validation guard the intake path; probes and retrains run with hard timeouts in a worker so a pathological CSV cannot hang the service.

## 7. Roadmap architecture notes (not built now)

The probe harness and prover are deliberately interface-shaped for extension: new probe types (robustness, fairness, drift) register against the same `Evidence`/`Finding` contract, and the prover's trainer abstraction is where SageMaker execution would slot in as an alternative backend. CI-gate mode is a thin wrapper: run audit, exit non-zero on any Proven finding.
