import { useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Database,
  FileCode2,
  Fingerprint,
  PackageCheck,
  TriangleAlert,
} from "lucide-react";

import type { Artifact, Mapping, Project } from "../types";

interface Props {
  project: Project;
  busy: boolean;
  onContinue: (mapping: Mapping) => void;
}

const kindIcon = {
  dataset: Database,
  model: PackageCheck,
  notebook: FileCode2,
  source: FileCode2,
  manifest: FileCode2,
};

export function ArtifactMap({ project, busy, onContinue }: Props) {
  const [mapping, setMapping] = useState<Mapping>(project.mapping);
  const complete = Boolean(
    mapping.dataset_artifact_id &&
    mapping.model_artifact_id &&
    mapping.notebook_artifact_id &&
    mapping.target_column &&
    mapping.split_column,
  );
  function selectFor(
    kind: "dataset" | "model" | "notebook",
    artifactId: string,
  ) {
    setMapping((current) => ({
      ...current,
      [`${kind}_artifact_id`]: artifactId,
    }));
  }

  return (
    <section className="workspace enter" aria-labelledby="map-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">State 2 · Evidence map</p>
          <h1 id="map-title">We found the pieces of the claim.</h1>
        </div>
        <div className="status-chip good">
          <CheckCircle2 aria-hidden="true" /> {project.artifacts.length}{" "}
          artifacts verified
        </div>
      </div>

      {project.warnings.length > 0 && (
        <div className="notice warning" role="status">
          <TriangleAlert aria-hidden="true" /> {project.warnings.join(" ")}
        </div>
      )}

      {project.source.benchmark_id === "uci_covid_surveillance_clean_v1" && (
        <div className="notice info" role="note">
          <CheckCircle2 aria-hidden="true" />
          <span>
            Public clean control from the{" "}
            <a
              href="https://archive.ics.uci.edu/dataset/567/covid%2B19%2Bsurveillance"
              target="_blank"
              rel="noreferrer"
            >
              UCI COVID-19 Surveillance dataset
            </a>
            , licensed CC BY 4.0 (DOI 10.24432/C5TC85). The bundled model and
            notebook are reproducible evaluation fixtures, not clinical
            validation.
          </span>
        </div>
      )}

      <div className="artifact-layout">
        <div className="artifact-list">
          {project.artifacts.map((artifact) => {
            const Icon = kindIcon[artifact.kind];
            return (
              <article className="artifact-card" key={artifact.artifact_id}>
                <div className="artifact-icon">
                  <Icon aria-hidden="true" />
                </div>
                <div className="artifact-main">
                  <div className="artifact-title">
                    <span>{artifact.filename}</span>
                    <span className={`support ${artifact.adapter_status}`}>
                      {artifact.adapter_status}
                    </span>
                  </div>
                  <p>
                    {artifact.kind} · {artifact.adapter} adapter ·{" "}
                    {(artifact.size_bytes / 1024).toFixed(1)} KB
                  </p>
                  <code>
                    <Fingerprint aria-hidden="true" /> sha256:
                    {artifact.sha256.slice(0, 12)}…
                  </code>
                </div>
              </article>
            );
          })}
        </div>

        <aside className="mapping-panel" aria-label="Artifact mapping controls">
          <p className="panel-label">Claim reconstruction</p>
          {(["dataset", "model", "notebook"] as const).map((kind) => (
            <label key={kind}>
              {kind[0]?.toUpperCase()}
              {kind.slice(1)} artifact
              <select
                value={mapping[`${kind}_artifact_id`] ?? ""}
                onChange={(event) => selectFor(kind, event.target.value)}
              >
                <option value="">Not mapped</option>
                {project.artifacts
                  .filter((artifact) => artifact.kind === kind)
                  .map((artifact: Artifact) => (
                    <option
                      key={artifact.artifact_id}
                      value={artifact.artifact_id}
                    >
                      {artifact.filename}
                    </option>
                  ))}
              </select>
            </label>
          ))}
          <div className="field-grid">
            <label>
              Target column
              <input
                value={mapping.target_column ?? ""}
                onChange={(event) =>
                  setMapping({ ...mapping, target_column: event.target.value })
                }
                placeholder="target"
              />
            </label>
            <label>
              Split column
              <input
                value={mapping.split_column ?? ""}
                onChange={(event) =>
                  setMapping({ ...mapping, split_column: event.target.value })
                }
                placeholder="split"
              />
            </label>
            <label>
              Entity column
              <input
                value={mapping.entity_column ?? ""}
                onChange={(event) =>
                  setMapping({
                    ...mapping,
                    entity_column: event.target.value || null,
                  })
                }
                placeholder="customer_id"
              />
            </label>
          </div>
          {!complete && (
            <p className="mapping-help">
              A complete audit needs one dataset, safe model, notebook, target,
              and split.
            </p>
          )}
          <button
            className="button primary wide"
            disabled={!complete || busy}
            onClick={() => onContinue(mapping)}
          >
            {busy ? "Saving map…" : "Confirm evidence map"}{" "}
            <ArrowRight aria-hidden="true" />
          </button>
        </aside>
      </div>
    </section>
  );
}
