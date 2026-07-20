# ADR-0001: One audit agent for the MVP

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

The audit needs semantic reasoning, typed deterministic tools, human clarification, and a coherent conclusion. Splitting this work among multiple agents would add handoff state, trace complexity, latency, cost, and additional failure modes before there is evidence that specialization improves audit quality.

## Decision

Use one `AuditAgent` powered by `gpt-5.6-sol` through the OpenAI Agents SDK and Responses API. The agent may call typed tools and pause for user input. Deterministic application code owns metrics, evidence records, and finding transitions.

## Consequences

- One investigation context is easier to replay and explain.
- There are no agent handoffs in the MVP.
- Tool and finding-policy boundaries must prevent the agent from inventing evidence.

## Reconsideration criteria

Add another agent only when a representative benchmark shows a measurable improvement in confirmed-finding precision/recall, completion rate, latency, cost, or maintainability that outweighs added orchestration complexity. The comparison must use the same benchmark set and preserve the Decision Trace contract.
