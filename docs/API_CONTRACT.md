# API Contract — PolygraphML

**Version:** 1.0 · **Base URL:** `/api/v1` · **Format:** JSON over HTTPS · **Auth:** none (local single-user MVP)

## Conventions

All responses envelope as `{ "data": ..., "error": null }` on success and `{ "data": null, "error": { "code", "message", "detail" } }` on failure. Timestamps are ISO 8601 UTC. IDs are ULIDs. Error codes: `INVALID_FILE`, `TARGET_NOT_FOUND`, `AUDIT_NOT_FOUND`, `AUDIT_IN_PROGRESS`, `PROBE_TIMEOUT`, `MODEL_OUTPUT_INVALID`, `INTERNAL`.

## Endpoints

### `POST /datasets`
Upload a dataset. `multipart/form-data`: `file` (CSV ≤ 50 MB), `target` (string, required), `time_column` (string, optional), `context` (string, optional free-text business context fed to the semantic auditor).

**201 →**
```json
{
  "data": {
    "dataset_id": "01J1ZK...",
    "n_rows": 10000,
    "n_features": 21,
    "target": "churned",
    "time_column": "signup_date",
    "profile": [
      {
        "name": "last_payment_status",
        "dtype": "categorical",
        "cardinality": 4,
        "missing_pct": 0.02,
        "sample_values": ["paid", "failed", "refunded", "chargeback"]
      }
    ]
  },
  "error": null
}
```
Errors: `400 INVALID_FILE`, `400 TARGET_NOT_FOUND`.

### `POST /audits`
Start an audit. Body: `{ "dataset_id": "...", "metric": "auc" | "accuracy" }` (metric defaults to `auc` for binary targets).

**202 →** `{ "data": { "audit_id": "01J1ZM...", "status": "profiling" }, "error": null }`

### `GET /audits/{audit_id}`
Poll audit state. Status ∈ `profiling | interrogating | probing | proving | composing | complete | failed_partial`.

**200 →**
```json
{
  "data": {
    "audit_id": "01J1ZM...",
    "status": "complete",
    "findings": [ Finding, ... ],
    "proofs": [ Proof, ... ],
    "verdict": Verdict
  },
  "error": null
}
```

### `GET /audits/{audit_id}/events`
Server-sent event stream of audit progress. Events (each `data:` payload is JSON):

| event | payload |
|---|---|
| `state` | `{ "status": "interrogating" }` |
| `narration` | `{ "text": "last_payment_status looks like it's populated after the outcome..." }` |
| `finding` | `Finding` (emitted on creation and on every status change) |
| `proof` | `Proof` |
| `verdict` | `Verdict` |
| `error` | `{ "code": "PROBE_TIMEOUT", "finding_id": "..." }` |

Supports `Last-Event-ID` resume.

### `POST /audits/{audit_id}/report`
Generate the stakeholder report. Body: `{ "audience": "executive" | "technical" }`.

**200 →** `{ "data": { "report_md": "# Model audit: churn_v3 ...", "generated_at": "..." }, "error": null }`

### `POST /audits/{audit_id}/report/email` *(stretch — may return 501)*
Body: `{ "to": "vp@company.com" }`. **202** on accept, **501** if the feature is not built.

## Schemas

### Finding
```json
{
  "finding_id": "01J1ZN...",
  "features": ["last_payment_status"],
  "type": "post_outcome | target_proxy | contamination | temporal | identifier",
  "severity": "critical | high | medium | low",
  "confidence": 0.92,
  "status": "suspected | probed | proven | cleared",
  "rationale": "Values like 'chargeback' and 'refunded' typically post-date a cancellation decision, so this field encodes the outcome it predicts.",
  "evidence": [ Evidence, ... ]
}
```

### Evidence
```json
{
  "probe": "single_feature_power | contamination | temporal | proxy_correlation",
  "metrics": { "auc": 0.97, "threshold": 0.85 },
  "detail": "Univariate stump on last_payment_status alone achieves AUC 0.97 against churned."
}
```

### Proof
```json
{
  "proof_id": "01J1ZP...",
  "features_removed": ["last_payment_status"],
  "model": "xgboost",
  "metric": "auc",
  "baseline": 0.982,
  "ablated": 0.714,
  "delta": -0.268,
  "verdict": "proven",
  "duration_ms": 4200
}
```

### Verdict
```json
{
  "honest_metric": { "name": "auc", "value": 0.714 },
  "claimed_metric": { "name": "auc", "value": 0.982 },
  "summary": "2 proven leaks, 1 cleared suspect. Reported performance is materially inflated.",
  "findings_by_severity": { "critical": 1, "high": 1, "medium": 0, "low": 0 }
}
```

## Contract invariants

Every numeric value in `Proof`, `Evidence`, and `Verdict` originates from the compute layer; the API layer never accepts model-generated numerics into those fields. A `Finding` may only reach `proven` via an attached `Proof` whose `delta` exceeds the materiality threshold. A dataset with zero findings must still return a `Verdict` with an explicit clean bill (`summary` states clearance; `honest_metric == claimed_metric`).
