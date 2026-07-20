# ADR-0004: Evidence-based SQS visibility and heartbeat timing

- **Status:** Accepted provisionally; production calibration pending
- **Date:** 2026-07-19

## Context

SQS delivery is at least once. If visibility expires before a live worker extends it, the same audit can be delivered concurrently. An arbitrarily large timeout slows retry recovery, while an arbitrarily small timeout increases duplicate processing.

## Decision

Use one shared `queue_visibility_seconds` value for the SQS queue, received-message visibility, DynamoDB audit lease, and worker heartbeat calculation. The heartbeat interval is the smaller of 60 seconds and one third of visibility, with a one-second floor.

The release tool computes a recommendation from captured per-audit durations:

```text
max(60 seconds, ceil(p95 duration × 4 + 30-second startup allowance))
```

The current four-case fixture sample has p95 `0.0755` seconds and recommends the 60-second floor. The configured 300-second visibility and 60-second heartbeat therefore cover fixture evidence. This is not production calibration: the gate remains open until at least 20 deployed live audit durations are captured and the tool reports `production_calibrated: true`.

## Consequences

- Terraform and the worker cannot drift to different visibility values.
- Every active job extends visibility before one third of the lease elapses.
- `benchmark-results/queue-timing.json` preserves the calculation and its limitations.
- A live latency change requires rerunning the calibration tool and reviewing Terraform, not silently changing a constant.
