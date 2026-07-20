# API Contract — PolygraphML

**Version:** 1.1 · **Base URL:** `/api/v1` · **Format:** JSON over HTTPS unless noted

## 1. Conventions

Successful responses use:

```json
{ "data": {}, "error": null }
```

Failed responses use:

```json
{
  "data": null,
  "error": {
    "code": "INVALID_ARTIFACT",
    "message": "The artifact could not be accepted.",
    "detail": {},
    "request_id": "req_01..."
  }
}
```

- Timestamps are ISO 8601 UTC.
- Public identifiers are ULIDs with type prefixes.
- Unknown JSON fields are rejected on write contracts unless explicitly documented.
- Create/start operations accept an `Idempotency-Key` header.
- Anonymous demo sessions use a short-lived bearer token and strict rate/cost quotas; there are no end-user accounts in the MVP.
- Artifact bytes travel directly between the browser and S3 using scoped presigned URLs.

Core errors: `INVALID_REQUEST`, `RATE_LIMITED`, `PROJECT_NOT_FOUND`, `INVALID_REPOSITORY`, `INVALID_ARTIFACT`, `UNSAFE_ARTIFACT`, `ARTIFACT_TOO_LARGE`, `MAPPING_INCOMPLETE`, `SCENARIO_INCOMPLETE`, `AUDIT_NOT_FOUND`, `AUDIT_NOT_RESUMABLE`, `QUESTION_NOT_FOUND`, `MODEL_OUTPUT_INVALID`, `PROBE_TIMEOUT`, `EXECUTION_UNSUPPORTED`, `INTERNAL`.

## 2. Sessions and benchmarks

### `POST /sessions`

Creates an anonymous, quota-bound demo session.

**201**

```json
{
  "data": {
    "access_token": "session-token-returned-once",
    "expires_at": "2026-07-19T02:00:00Z",
    "limits": { "max_projects": 3, "max_live_audits": 2 }
  },
  "error": null
}
```

### `GET /benchmarks`

Lists curated benchmark projects with pinned versions, licenses, expected audit coverage, and whether they use live OpenAI analysis or saved fixture events.

### `POST /projects/from-benchmark`

Body: `{ "benchmark_id": "benchmark_bank_marketing_v1" }`.

Creates an ordinary project from immutable benchmark artifacts so all later endpoints are identical to a user submission.

## 3. Projects and source intake

### `POST /projects`

Creates a project from either a public GitHub repository or an upload session.

**GitHub body**

```json
{
  "name": "churn-model-review",
  "source": {
    "type": "github",
    "repository_url": "https://github.com/example/churn-model",
    "ref": "main"
  }
}
```

**Upload body**

```json
{
  "name": "churn-model-review",
  "source": { "type": "upload" }
}
```

**202** for GitHub import or **201** for empty upload project:

```json
{
  "data": {
    "project_id": "prj_01...",
    "status": "importing",
    "source": {
      "type": "github",
      "repository_url": "https://github.com/example/churn-model",
      "requested_ref": "main",
      "resolved_commit": null
    }
  },
  "error": null
}
```

The import must resolve a mutable ref to a commit SHA before the project becomes `ready_for_mapping`. The MVP accepts public repositories only.

### `POST /projects/{project_id}/artifacts/presign`

Requests upload URLs after client-side file selection. Metadata is validated before URLs are issued.

```json
{
  "artifacts": [
    {
      "client_id": "dataset",
      "filename": "evaluation.parquet",
      "kind": "dataset",
      "size_bytes": 1842031,
      "sha256": "hex-sha256",
      "media_type": "application/vnd.apache.parquet"
    },
    {
      "client_id": "model",
      "filename": "model.skops",
      "kind": "model",
      "size_bytes": 42031,
      "sha256": "hex-sha256",
      "media_type": "application/octet-stream"
    }
  ]
}
```

**200** returns one short-lived `PUT` URL and required headers per artifact. Presigned data and URLs are never written to application logs.

### `POST /projects/{project_id}/artifacts/complete`

Confirms completed uploads. The backend verifies existence, size, checksum, type, and safety policy before creating `Artifact` records.

### `GET /projects/{project_id}`

Returns source status, detected artifacts, inferred mappings, validation warnings, and scenario revision.

### `PATCH /projects/{project_id}/mapping`

Confirms or corrects artifact roles and source locations.

```json
{
  "dataset_artifact_id": "art_01...",
  "model_artifact_id": "art_02...",
  "notebook_artifact_id": "art_03...",
  "target_column": "churned",
  "time_column": "event_time",
  "entity_column": "customer_id",
  "reported_metric_source": {
    "artifact_id": "art_03...",
    "location": "cell:42"
  }
}
```

`model_artifact_id` may be omitted when the notebook/repository deterministically trains the model. A dataset-only project is marked `preflight_only`.

### `PUT /projects/{project_id}/scenario`

Creates a new immutable scenario revision.

```json
{
  "target_definition": "Customer cancels within the next 30 days",
  "row_entity": "One customer snapshot",
  "decision_time": "Immediately before the retention campaign selects customers",
  "prediction_horizon": "30 days",
  "split_unit": "customer_id",
  "intended_metric": "roc_auc",
  "positive_label": "1",
  "notes": "Features must be available before campaign selection."
}
```

## 4. Audits

### `POST /audits`

Starts a durable audit. Requires an `Idempotency-Key`.

```json
{
  "project_id": "prj_01...",
  "scenario_revision": 1,
  "mode": "complete_audit"
}
```

Modes are `complete_audit` and `dataset_preflight`. A project that lacks model or reproducible pipeline evidence cannot request `complete_audit`.

**202**

```json
{
  "data": {
    "audit_id": "aud_01...",
    "status": "queued",
    "created_at": "2026-07-18T18:40:00Z",
    "events_url": "/api/v1/audits/aud_01.../events"
  },
  "error": null
}
```

### `GET /audits/{audit_id}`

Returns the current checkpoint and all committed result summaries.

Statuses:

`validating | queued | reconstructing | reproducing | interrogating | waiting_for_user | probing | correcting | composing | complete | failed_partial | failed`

**200**

```json
{
  "data": {
    "audit_id": "aud_01...",
    "project_id": "prj_01...",
    "status": "complete",
    "reproduction_tier": "exact_supported",
    "last_event_sequence": 84,
    "open_questions": [],
    "findings": [],
    "metric_comparison": {},
    "verdict": {},
    "provenance": {
      "source_commit": "40-char-sha",
      "artifact_hashes": ["sha256:..."],
      "evaluator_version": "0.1.0",
      "agent_model": "gpt-5.6-sol",
      "prompt_schema_version": "audit-v1"
    }
  },
  "error": null
}
```

### `GET /audits/{audit_id}/events`

Streams ordered Decision Trace events as `text/event-stream`. The client sends `Last-Event-ID` or `after_sequence` to resume. A polling client may use `Accept: application/json` with `after_sequence`.

Example SSE frame:

```text
id: evt_01...
event: hypothesis
data: {"sequence":21,"actor":"agent","payload":{"hypothesis_id":"hyp_01..."}}
```

Event names:

| Event | Purpose |
|---|---|
| `audit_state` | Durable state transition or checkpoint |
| `assumption` | Declared scenario or reconstruction assumption |
| `question` / `answer` | Human-in-the-loop exchange |
| `hypothesis` | Falsifiable concern and proposed probe |
| `tool_started` / `tool_result` | Deterministic operation lifecycle |
| `evidence` | Persisted compute-owned evidence |
| `correction` | Applied or proposed repair |
| `finding_changed` | Finding status/severity/confidence transition |
| `reasoning_summary` | Optional sanitized model summary, never raw chain-of-thought |
| `warning` / `retry` / `error` | Degradation and operational visibility |
| `verdict` | Final audit result |

### `POST /audits/{audit_id}/answers`

Answers the current material question and enqueues a resume operation.

```json
{
  "question_id": "qst_01...",
  "answer": "The value is available only after the call finishes.",
  "scenario_patch": {
    "notes": "Call duration is not available at campaign selection time."
  }
}
```

**202** returns `status: queued`. Repeating the same idempotent answer must not duplicate the resume job.
`Idempotency-Key` is required on this mutation; repeating the same key returns the existing queued audit and re-attempts the durable enqueue without changing the answer.

### `POST /audits/{audit_id}/report`

Body: `{ "audience": "technical" | "executive", "format": "markdown" }`.

**202** for generation or **200** if the immutable report already exists. The final report resource provides a scoped download URL. PDF is optional; email delivery is not part of the MVP contract.

## 5. Core schemas

### Artifact

```json
{
  "artifact_id": "art_01...",
  "kind": "dataset | model | notebook | source | manifest",
  "filename": "model.skops",
  "sha256": "hex-sha256",
  "size_bytes": 42031,
  "adapter": "skops",
  "adapter_status": "supported | limited | unsupported | rejected",
  "validation_notes": []
}
```

### Question

```json
{
  "question_id": "qst_01...",
  "text": "Is call_duration known before or after the call?",
  "why_it_matters": "Feature availability determines whether this is post-outcome leakage.",
  "affected_hypothesis_ids": ["hyp_01..."],
  "answer_type": "single_choice",
  "options": ["before", "after", "depends", "unknown"],
  "blocking": true,
  "status": "open"
}
```

### Hypothesis

```json
{
  "hypothesis_id": "hyp_01...",
  "mechanism": "post_outcome",
  "features": ["call_duration"],
  "assumptions": ["Predictions are made before a call begins."],
  "rationale_summary": "Call duration normally exists only after contact is completed.",
  "requested_probe": "feature_availability",
  "falsification_condition": "The prediction is made after the completed call.",
  "source_refs": ["notebook.ipynb#cell=12", "dataset:call_duration"]
}
```

### Evidence

```json
{
  "evidence_id": "evd_01...",
  "hypothesis_id": "hyp_01...",
  "probe": "feature_availability",
  "tool_version": "feature_availability@1",
  "observation": "The pipeline computes the feature from completed-call records.",
  "metrics": {},
  "source_refs": ["features.py#L42", "user_answer:qst_01..."],
  "limitations": [],
  "computed_at": "2026-07-18T18:42:00Z"
}
```

### Finding

```json
{
  "finding_id": "fnd_01...",
  "mechanism": "post_outcome | target_proxy | split_contamination | group_contamination | temporal | preprocessing | metric_mismatch | other",
  "features": ["call_duration"],
  "status": "needs_context | suspected | tested | confirmed | cleared | inconclusive",
  "severity": "critical | high | medium | low | info",
  "confidence": 0.94,
  "conclusion": "call_duration is unavailable at the stated campaign decision time.",
  "hypothesis_ids": ["hyp_01..."],
  "evidence_ids": ["evd_01...", "evd_02..."],
  "correction_id": "cor_01...",
  "what_would_change_this": "A documented post-call prediction scenario."
}
```

### MetricComparison

```json
{
  "metric": "roc_auc",
  "reported": {
    "value": 1.0,
    "protocol_id": "reported_claim_unverified",
    "reproduction_tier": "reported_claim",
    "provenance": "training.ipynb#cell=2"
  },
  "reproduced": {
    "value": 1.0,
    "tolerance": 0.005,
    "protocol_id": "proto_original_v1",
    "reproduction_tier": "exact_supported",
    "provenance": "result:reproduction.json"
  },
  "corrected": {
    "value": 0.8627956989247312,
    "tolerance": 0.005,
    "protocol_id": "proto_corrected_v1",
    "reproduction_tier": "exact_supported",
    "provenance": "result:corrected.json"
  },
  "reproduction_status": "within_tolerance"
}
```

### AuditEvent

```json
{
  "event_id": "evt_01...",
  "audit_id": "aud_01...",
  "sequence": 21,
  "type": "hypothesis",
  "actor": "user | agent | tool | system",
  "created_at": "2026-07-18T18:41:00Z",
  "payload": {},
  "provenance_refs": []
}
```

### Verdict

```json
{
  "trust_state": "materially_inflated | partially_supported | supported | inconclusive",
  "summary": "The reported score is reproducible under the submitted split but materially inflated for the stated decision scenario.",
  "metric_comparison_id": "met_01...",
  "finding_counts": {
    "confirmed": 1,
    "cleared": 5,
    "inconclusive": 1
  },
  "unsupported_checks": ["onnx_preprocessing_equivalence"]
}
```

## 6. Contract invariants

1. Numeric fields in `Evidence`, `MetricComparison`, and quantitative verdict summaries originate from versioned compute outputs, never free-form model text.
2. A finding cannot become `confirmed` solely because an ablation reduces performance.
3. `reasoning_summary` events are labeled summaries and cannot be cited as deterministic evidence.
4. Every event sequence is monotonic and replayable; retries cannot create conflicting events for one idempotency key.
5. Every metric names its evaluation protocol, reproduction tier, and provenance.
6. A clean result states the tested scope and scenario; it does not claim that the model is universally safe.
7. A rejected artifact is never loaded or executed.
8. SQS messages, API responses, events, logs, and exports never contain the OpenAI API key.
