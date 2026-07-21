import type { components } from "./generated/api";

type Schemas = components["schemas"];
type RequiredFields<T, K extends keyof T> = T & Required<Pick<T, K>>;

export type ArtifactKind = Schemas["ArtifactKind"];
export type Artifact = RequiredFields<
  Schemas["Artifact"],
  "source_ref" | "upload_status" | "validation_notes"
>;
export type Mapping = RequiredFields<
  Schemas["ArtifactMapping"],
  | "dataset_artifact_id"
  | "model_artifact_id"
  | "notebook_artifact_id"
  | "target_column"
  | "entity_column"
  | "time_column"
  | "split_column"
  | "reported_metric_source"
>;
export type Scenario = RequiredFields<
  Schemas["Scenario"],
  "revision" | "positive_label" | "notes"
>;
export type Project = Omit<
  RequiredFields<
    Schemas["ProjectResponse"],
    "mapping" | "scenarios" | "warnings" | "feature_context"
  >,
  "artifacts" | "mapping" | "scenarios"
> & {
  artifacts: Artifact[];
  mapping: Mapping;
  scenarios: Scenario[];
};

export type AuditEvent = RequiredFields<
  Schemas["AuditEvent"],
  "created_at" | "provenance_refs"
>;
export type Question = RequiredFields<Schemas["Question"], "options">;
export type MetricValue = RequiredFields<Schemas["MetricValue"], "tolerance">;
export type MetricComparison = Omit<
  RequiredFields<
    Schemas["MetricComparison"],
    "reported" | "reproduced" | "corrected"
  >,
  "reported" | "reproduced" | "corrected"
> & {
  reported: MetricValue | null;
  reproduced: MetricValue | null;
  corrected: MetricValue | null;
};
export type Finding = RequiredFields<
  Schemas["Finding"],
  "evidence_ids" | "hypothesis_ids" | "correction_id"
>;
export type Provenance = RequiredFields<
  Schemas["Provenance"],
  | "source_commit"
  | "artifact_hashes"
  | "package_versions"
  | "split_hash"
  | "feature_order"
  | "agent_execution"
  | "compute_execution"
>;
export type Verdict = RequiredFields<Schemas["Verdict"], "unsupported_checks">;
export type Audit = Omit<
  RequiredFields<
    Schemas["AuditResponse"],
    "metric_comparison" | "verdict" | "provenance"
  >,
  "metric_comparison" | "findings" | "open_questions" | "provenance" | "verdict"
> & {
  metric_comparison: MetricComparison | null;
  findings: Finding[];
  open_questions: Question[];
  provenance: Provenance;
  verdict: Verdict | null;
};

export type RepairBundle = RequiredFields<
  Schemas["RepairBundleResponse"],
  "download_url" | "file_hashes" | "limitations" | "sha256" | "size_bytes"
>;
export type Version = Schemas["VersionResponse"];
export type AuditReport = Schemas["AuditReport"];

export interface Readiness {
  status: "ready";
  agent_mode: "fixture" | "live";
  live_agent_ready: boolean;
}
