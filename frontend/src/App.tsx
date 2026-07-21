import { useCallback, useEffect, useRef, useState } from "react";
import {
  FlaskConical,
  Hexagon,
  Radio,
  TriangleAlert,
  Wifi,
} from "lucide-react";

import { api, ApiError, artifactKind, sha256 } from "./api";
import { ArtifactMap } from "./components/ArtifactMap";
import { AuditWorkspace } from "./components/AuditWorkspace";
import { Intake } from "./components/Intake";
import { ScenarioForm } from "./components/ScenarioForm";
import { Stepper } from "./components/Stepper";
import type {
  Audit,
  AuditEvent,
  Mapping,
  Project,
  Question,
  Readiness,
  RepairBundle,
  Scenario,
  Version,
} from "./types";

type View = "intake" | "mapping" | "scenario" | "audit";
const AUDIT_KEY = "polygraphml.active-audit";
const PROJECT_KEY = "polygraphml.active-project";
const FRONTEND_BUILD_SHA = import.meta.env.VITE_BUILD_SHA ?? "local";

export function App() {
  const [view, setView] = useState<View>("intake");
  const [project, setProject] = useState<Project | null>(null);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [version, setVersion] = useState<Version | null>(null);
  const [eventTransport, setEventTransport] = useState<
    "idle" | "sse" | "reconnecting" | "polling"
  >("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<string | null>(null);
  const [reportAudience, setReportAudience] = useState<
    "technical" | "executive"
  >("technical");
  const [repair, setRepair] = useState<RepairBundle | null>(null);
  const lastSequence = useRef(0);
  const lastEventId = useRef<string | null>(null);
  const activeAuditId = audit?.audit_id;
  const activeAuditStatus = audit?.status;

  const fail = useCallback((cause: unknown) => {
    setBusy(false);
    setError(
      cause instanceof ApiError
        ? `${cause.message} (${cause.code})`
        : "Something unexpected interrupted this step.",
    );
  }, []);

  const refreshAudit = useCallback(async (auditId: string) => {
    const [nextAudit, nextEvents] = await Promise.all([
      api.audit(auditId),
      api.events(auditId, lastSequence.current),
    ]);
    setAudit(nextAudit);
    if (nextEvents.length > 0) {
      lastSequence.current =
        nextEvents.at(-1)?.sequence ?? lastSequence.current;
      lastEventId.current = nextEvents.at(-1)?.event_id ?? lastEventId.current;
      setEvents((current) => {
        const known = new Set(current.map((event) => event.event_id));
        return [
          ...current,
          ...nextEvents.filter((event) => !known.has(event.event_id)),
        ];
      });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadReadiness() {
      for (let attempt = 0; attempt < 10; attempt += 1) {
        try {
          const [status, build] = await Promise.all([
            api.readiness(),
            api.version(),
          ]);
          if (!cancelled) {
            setReadiness(status);
            setVersion(build);
          }
          return;
        } catch (cause) {
          if (attempt === 9) {
            if (!cancelled) fail(cause);
            return;
          }
          await new Promise((resolve) => window.setTimeout(resolve, 300));
        }
      }
    }
    void loadReadiness();
    const auditId = sessionStorage.getItem(AUDIT_KEY);
    const projectId = sessionStorage.getItem(PROJECT_KEY);
    if (auditId && projectId) {
      void Promise.all([api.project(projectId), refreshAudit(auditId)])
        .then(([restored]) => {
          setProject(restored);
          setView("audit");
          setBusy(false);
        })
        .catch(() => {
          sessionStorage.removeItem(AUDIT_KEY);
          sessionStorage.removeItem(PROJECT_KEY);
          setBusy(false);
        });
    }
    return () => {
      cancelled = true;
    };
  }, [fail, refreshAudit]);

  useEffect(() => {
    if (
      !activeAuditId ||
      view !== "audit" ||
      ["complete", "failed", "failed_partial", "waiting_for_user"].includes(
        activeAuditStatus ?? "",
      )
    ) {
      return;
    }
    const auditId = activeAuditId;
    const controller = new AbortController();
    let cancelled = false;
    let reconnectTimer: number | undefined;
    let pollingTimer: number | undefined;

    const appendEvent = (event: AuditEvent) => {
      lastSequence.current = Math.max(lastSequence.current, event.sequence);
      lastEventId.current = event.event_id;
      setEvents((current) =>
        current.some((item) => item.event_id === event.event_id)
          ? current
          : [...current, event],
      );
    };

    const poll = async () => {
      try {
        await refreshAudit(auditId);
      } catch (cause) {
        if (!cancelled) fail(cause);
      }
    };

    const connect = async (attempt: number) => {
      if (cancelled) return;
      setEventTransport(attempt === 0 ? "sse" : "reconnecting");
      try {
        await api.streamEvents(
          auditId,
          lastSequence.current,
          lastEventId.current,
          appendEvent,
          controller.signal,
        );
        if (cancelled) return;
        const latest = await api.audit(auditId);
        setAudit(latest);
        if (
          ["complete", "failed", "failed_partial", "waiting_for_user"].includes(
            latest.status,
          )
        ) {
          setEventTransport("idle");
        }
        if (
          ![
            "complete",
            "failed",
            "failed_partial",
            "waiting_for_user",
          ].includes(latest.status)
        ) {
          const delay = Math.min(500 * 2 ** attempt, 5_000);
          reconnectTimer = window.setTimeout(
            () => void connect(attempt + 1),
            delay,
          );
        }
      } catch {
        if (cancelled || controller.signal.aborted) return;
        if (attempt < 2) {
          const delay = Math.min(500 * 2 ** attempt, 5_000);
          reconnectTimer = window.setTimeout(
            () => void connect(attempt + 1),
            delay,
          );
          return;
        }
        setEventTransport("polling");
        await poll();
        pollingTimer = window.setInterval(() => void poll(), 1_500);
      }
    };

    void connect(0);
    return () => {
      cancelled = true;
      controller.abort();
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      if (pollingTimer) window.clearInterval(pollingTimer);
    };
  }, [activeAuditId, activeAuditStatus, fail, refreshAudit, view]);

  async function chooseBenchmark(
    benchmarkId = "uci_bank_marketing_duration_v1",
  ) {
    setBusy(true);
    setError(null);
    try {
      const created = await api.benchmarkProject(benchmarkId);
      setProject(created);
      setView("mapping");
    } catch (cause) {
      fail(cause);
    } finally {
      setBusy(false);
    }
  }

  async function chooseGithub(url: string, ref: string) {
    setBusy(true);
    setError(null);
    try {
      const created = await api.githubProject(url, ref);
      setProject(created);
      setView("mapping");
    } catch (cause) {
      fail(cause);
    } finally {
      setBusy(false);
    }
  }

  async function chooseUpload(files: File[]) {
    const accepted = files
      .map((file) => ({ file, kind: artifactKind(file) }))
      .filter((item) => item.kind !== null);
    if (accepted.length === 0) {
      setError(
        "Choose a supported dataset, model, or notebook file. Pickle-family formats are not accepted.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api.uploadProject("Uploaded model evidence");
      const declarations = await Promise.all(
        accepted.map(async ({ file, kind }, index) => ({
          client_id: `upload_${index}`,
          filename: file.name,
          kind,
          size_bytes: file.size,
          sha256: await sha256(file),
          media_type: file.type || "application/octet-stream",
        })),
      );
      const intents = await api.declareUploads(
        created.project_id,
        declarations,
      );
      for (const intent of intents.uploads) {
        const selected = accepted.find(
          (_, index) => `upload_${index}` === intent.client_id,
        );
        if (selected)
          await api.putUpload(intent.url, selected.file, intent.headers);
      }
      const completed = await api.completeUploads(
        created.project_id,
        intents.uploads.map((intent) => intent.artifact_id),
      );
      setProject(completed);
      setView("mapping");
    } catch (cause) {
      fail(cause);
    } finally {
      setBusy(false);
    }
  }

  async function saveMapping(mapping: Mapping) {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.mapProject(project.project_id, mapping);
      setProject(updated);
      setView("scenario");
    } catch (cause) {
      fail(cause);
    } finally {
      setBusy(false);
    }
  }

  async function startAudit(scenario: Scenario) {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.scenario(project.project_id, scenario);
      const revision = updated.scenarios.at(-1)?.revision ?? 1;
      const started = await api.startAudit(project.project_id, revision);
      setProject(updated);
      setAudit(started);
      setEvents([]);
      lastSequence.current = 0;
      lastEventId.current = null;
      setView("audit");
      sessionStorage.setItem(AUDIT_KEY, started.audit_id);
      sessionStorage.setItem(PROJECT_KEY, project.project_id);
      await refreshAudit(started.audit_id);
    } catch (cause) {
      fail(cause);
    } finally {
      setBusy(false);
    }
  }

  async function answer(question: Question, value: string) {
    if (!audit) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.answer(
        audit.audit_id,
        question.question_id,
        value,
      );
      setAudit(updated);
      await refreshAudit(audit.audit_id);
    } catch (cause) {
      fail(cause);
    } finally {
      setBusy(false);
    }
  }

  async function generateReport(audience: "technical" | "executive") {
    if (!audit) return;
    setBusy(true);
    setError(null);
    try {
      const generated = await api.report(audit.audit_id, audience);
      setReport(generated.content);
      setReportAudience(audience);
    } catch (cause) {
      fail(cause);
    } finally {
      setBusy(false);
    }
  }

  async function generateRepair() {
    if (!audit) return;
    setBusy(true);
    setError(null);
    try {
      setRepair(await api.repairBundle(audit.audit_id));
    } catch (cause) {
      fail(cause);
    } finally {
      setBusy(false);
    }
  }

  async function downloadRepair() {
    if (!repair?.download_url || !audit) return;
    setBusy(true);
    setError(null);
    try {
      const blob = await api.downloadRepair(repair.download_url);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `polygraphml-${audit.audit_id}-repair.zip`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      fail(cause);
    } finally {
      setBusy(false);
    }
  }

  function restart() {
    sessionStorage.removeItem(AUDIT_KEY);
    sessionStorage.removeItem(PROJECT_KEY);
    setView("intake");
    setProject(null);
    setAudit(null);
    setEvents([]);
    setReport(null);
    setRepair(null);
    setError(null);
    lastSequence.current = 0;
    lastEventId.current = null;
  }

  const currentStep =
    view === "intake"
      ? 1
      : view === "mapping"
        ? 2
        : view === "scenario"
          ? 3
          : audit?.status === "complete"
            ? 7
            : audit?.status === "correcting"
              ? 6
              : audit?.status === "waiting_for_user" ||
                  audit?.status === "probing" ||
                  audit?.status === "interrogating"
                ? 5
                : 4;
  const initialScenario =
    project?.scenarios.at(-1) ??
    ({
      revision: 1,
      target_definition: "Outcome within the stated horizon",
      row_entity: "One prediction row",
      decision_time: "Before the operational decision",
      prediction_horizon: "30 days",
      split_unit: project?.mapping.entity_column ?? "entity",
      intended_metric: "roc_auc",
      positive_label: "1",
      notes: "",
    } satisfies Scenario);

  return (
    <div className="app-frame">
      <header className="topbar">
        <button
          className="brand"
          onClick={restart}
          aria-label="PolygraphML home"
        >
          <span className="brand-mark">
            <Hexagon aria-hidden="true" />
            <Radio aria-hidden="true" />
          </span>
          <span>
            Polygraph<span>ML</span>
          </span>
        </button>
        <div className="mode-area">
          {audit?.provenance.agent_execution?.mode === "live" &&
          audit.provenance.agent_execution.provider === "openai" ? (
            <span className="mode-badge live">
              <Wifi aria-hidden="true" /> Live ·{" "}
              {audit.provenance.agent_execution.resolved_model ??
                audit.provenance.agent_execution.requested_model}
            </span>
          ) : audit?.provenance.agent_execution?.mode === "degraded" ? (
            <span className="mode-badge degraded">
              <TriangleAlert aria-hidden="true" /> Degraded · fixture fallback
            </span>
          ) : audit?.provenance.agent_execution?.mode === "fixture" ? (
            <span className="mode-badge fixture">
              <FlaskConical aria-hidden="true" /> Fixture · no live model call
            </span>
          ) : readiness === null ? (
            <span className="mode-badge">
              <Radio aria-hidden="true" /> Connecting to audit service…
            </span>
          ) : (
            <span className="mode-badge">
              <Radio aria-hidden="true" /> Audit service ready ·{" "}
              {readiness.live_agent_ready
                ? "live configured"
                : "fixture configured"}
            </span>
          )}
          {version && (
            <span
              className="build-badge"
              title={`Frontend ${FRONTEND_BUILD_SHA}; API ${version.build_sha}`}
            >
              {version.release_version} · FE {FRONTEND_BUILD_SHA.slice(0, 8)} ·
              API {version.build_sha.slice(0, 8)}
            </span>
          )}
          <a
            href="https://github.com/Iguta/polygraph-ml/tree/main/docs"
            target="_blank"
            rel="noreferrer"
          >
            Docs
          </a>
        </div>
      </header>
      <Stepper current={currentStep} />
      {error && (
        <div className="global-error" role="alert">
          <TriangleAlert aria-hidden="true" />
          <span>{error}</span>
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}
      <main className="content-frame">
        {view === "intake" && (
          <Intake
            busy={busy}
            onBenchmark={() => void chooseBenchmark()}
            onPublicBenchmark={() =>
              void chooseBenchmark("uci_covid_surveillance_clean_v1")
            }
            onGithub={(url, ref) => void chooseGithub(url, ref)}
            onUpload={(files) => void chooseUpload(files)}
          />
        )}
        {view === "mapping" && project && (
          <ArtifactMap
            project={project}
            busy={busy}
            onContinue={(mapping) => void saveMapping(mapping)}
          />
        )}
        {view === "scenario" && project && (
          <ScenarioForm
            initial={initialScenario}
            busy={busy}
            onSubmit={(scenario) => void startAudit(scenario)}
          />
        )}
        {view === "audit" && audit && project && (
          <AuditWorkspace
            audit={audit}
            project={project}
            events={events}
            busy={busy}
            report={report}
            reportAudience={reportAudience}
            repair={repair}
            eventTransport={eventTransport}
            backendVersion={version}
            onAnswer={(question, value) => void answer(question, value)}
            onReport={(audience) => void generateReport(audience)}
            onRepair={() => void generateRepair()}
            onDownloadRepair={() => void downloadRepair()}
            onRestart={restart}
          />
        )}
        {busy && !project && view !== "intake" && (
          <div className="loading-screen" role="status">
            <ActivityIndicator />
            <p>Securing the workspace…</p>
          </div>
        )}
      </main>
      <footer className="site-footer">
        <span>PolygraphML · evidence-backed QA for ML systems</span>
        <span>Never upload pickle files or secrets.</span>
      </footer>
    </div>
  );
}

function ActivityIndicator() {
  return (
    <span className="activity-indicator" aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}
