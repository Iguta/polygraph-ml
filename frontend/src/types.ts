export type ArtifactKind =
  "dataset" | "model" | "notebook" | "source" | "manifest";

export interface Artifact {
  artifact_id: string;
  kind: ArtifactKind;
  filename: string;
  sha256: string;
  size_bytes: number;
  adapter: string;
  adapter_status: "supported" | "limited" | "unsupported" | "rejected";
  validation_notes: string[];
  source_ref: string | null;
  upload_status: "pending" | "complete";
}

export interface Mapping {
  dataset_artifact_id: string | null;
  model_artifact_id: string | null;
  notebook_artifact_id: string | null;
  target_column: string | null;
  entity_column: string | null;
  time_column: string | null;
  split_column: string | null;
  reported_metric_source: { artifact_id: string; location: string } | null;
}

export interface Scenario {
  revision: number;
  target_definition: string;
  row_entity: string;
  decision_time: string;
  prediction_horizon: string;
  split_unit: string;
  intended_metric: "roc_auc" | "accuracy" | "f1";
  positive_label: string;
  notes: string;
}

export interface Project {
  project_id: string;
  name: string;
  status: string;
  source: {
    type: "benchmark" | "github" | "upload";
    resolved_commit?: string | null;
    repository_url?: string | null;
    benchmark_id?: string | null;
  };
  artifacts: Artifact[];
  mapping: Mapping;
  scenarios: Scenario[];
  warnings: string[];
}

export interface AuditEvent {
  event_id: string;
  sequence: number;
  type: string;
  actor: "user" | "agent" | "tool" | "system";
  created_at: string;
  payload: Record<string, any>;
  provenance_refs: string[];
}

export interface Question {
  question_id: string;
  text: string;
  why_it_matters: string;
  options: string[];
  answer_type: "single_choice" | "free_text";
}

export interface MetricValue {
  value: number;
  provenance: string;
  protocol_id: string | null;
  tolerance: number | null;
}

export interface Finding {
  finding_id: string;
  mechanism: string;
  features: string[];
  status: string;
  severity: string;
  confidence: number;
  conclusion: string;
  what_would_change_this: string;
  evidence_ids: string[];
}

export interface Audit {
  audit_id: string;
  project_id: string;
  status: string;
  checkpoint: string;
  last_event_sequence: number;
  reproduction_tier: string | null;
  metric_comparison: {
    metric: string;
    reported: MetricValue | null;
    reproduced: MetricValue | null;
    corrected: MetricValue | null;
    reproduction_status: string;
  } | null;
  findings: Finding[];
  open_questions: Question[];
  verdict: {
    trust_state: string;
    summary: string;
    finding_counts: Record<string, number>;
    unsupported_checks: string[];
  } | null;
  provenance: {
    source_commit: string | null;
    artifact_hashes: string[];
    agent_model: string;
    random_seed: number;
    package_versions: Record<string, string>;
    split_hash: string | null;
    feature_order: string[];
  };
}

export interface Readiness {
  status: string;
  agent_mode: "fixture" | "live";
  live_agent_ready: boolean;
}
