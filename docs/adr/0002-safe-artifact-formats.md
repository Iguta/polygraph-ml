# ADR-0002: Safe artifact formats and execution boundary

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

Model and repository submissions are untrusted. Python pickle-family formats can execute arbitrary code during loading, while arbitrary notebook execution can expose application credentials or infrastructure.

## Decision

The initial safe paths are CSV/Parquet datasets, static `.ipynb`/Python inspection, and allowlisted `.skops` objects. XGBoost JSON receives structural validation; XGBoost UBJ and ONNX are recognized but labeled limited until P1 execution/equivalence adapters ship.

Reject remotely supplied pickle, joblib, cloudpickle, arbitrary executable serialization, and JSON that does not validate as a supported model format. The API and agent coordinator never execute submitted source. Any future code execution occurs only in a disposable no-secret task with narrow storage permissions, restricted egress, and resource/time limits.

## Consequences

- Some repositories receive a partial/static reproduction tier.
- Safety failures are visible and actionable rather than bypassed.
- New formats require a versioned adapter, threat review, fixtures, and negative tests.
