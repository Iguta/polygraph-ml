# How Codex Built PolygraphML

*This document satisfies the OpenAI Build Week requirement to document Codex usage, and it is also an honest engineering log. Session IDs and log excerpts are added during the build — placeholders below are marked `TODO` and must be filled before submission.*

## Codex Session ID

`TODO: capture via /feedback during the Day 1 scaffolding session and paste here.`

## The role Codex played

Codex was the primary build agent for PolygraphML across all three days, working from the specifications in this repository ([TDD](TDD.md), [API_CONTRACT](API_CONTRACT.md), [SOLUTION_ARCHITECTURE](SOLUTION_ARCHITECTURE.md)).

**Scaffolding and services (Day 1).** Codex generated the FastAPI application structure, the intake and profiling service, the OpenAI Agents SDK orchestration loop, and the structured-output integration for the semantic auditor — including the retry-on-validation-failure path.

**The adversarial test suite (Days 1–2) — the part we're proudest of.** Codex authored the synthetic dataset generator that plants five known leak types (target proxy, post-outcome field, cross-split duplication, temporal bleed, identifier) plus a fully clean control, and then wrote the pytest suite asserting that PolygraphML catches every planted leak and files zero false accusations against the clean dataset. The tool that audits models is itself audited against manufactured ground truth. `TODO: link the test run output.`

**Probe harness and prover (Days 1–2).** Codex implemented the four probes and the ablation retraining loop, including the fixed-seed reproducibility guarantees and the materiality threshold that gates a finding's promotion to Proven.

**Frontend and verification (Day 2–3).** Codex built the React dashboard's five states and the SSE client, then verified the rendered result with a Playwright smoke test covering the full demo path — upload, interrogation, proof, verdict, report.

**Debugging log.** `TODO: keep a short honest list here of 2–3 real bugs Codex diagnosed and fixed (e.g., SSE resume, XGBoost seed nondeterminism) — specific war stories read as genuine effort.`

## Division of labor

The specifications, product decisions, scope cuts, and demo design are the builder's; the implementation, tests, and mechanical debugging are Codex's. Every Codex-generated component was reviewed before merge to `dev`, and `main` only ever received states with the synthetic suite green.
