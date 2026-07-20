import { useMemo, useState } from "react";
import clsx from "clsx";
import {
  Activity,
  ArrowDown,
  BrainCircuit,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Clock3,
  Download,
  FileCheck2,
  FlaskConical,
  HelpCircle,
  RotateCcw,
  Scale,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  TriangleAlert,
} from "lucide-react";

import type {
  Audit,
  AuditEvent,
  Finding,
  MetricValue,
  Project,
  Question,
} from "../types";

interface Props {
  audit: Audit;
  project: Project;
  events: AuditEvent[];
  busy: boolean;
  report: string | null;
  onAnswer: (question: Question, answer: string) => void;
  onReport: () => void;
  onRestart: () => void;
}

const eventMeta: Record<
  string,
  { label: string; icon: typeof Activity; tone: string }
> = {
  audit_state: { label: "Audit state", icon: Activity, tone: "neutral" },
  hypothesis: { label: "Hypothesis", icon: BrainCircuit, tone: "violet" },
  reasoning_summary: { label: "Model summary", icon: Sparkles, tone: "violet" },
  tool_result: { label: "Tool result", icon: TerminalSquare, tone: "cyan" },
  evidence: { label: "Computed evidence", icon: FlaskConical, tone: "green" },
  correction: { label: "Correction", icon: Scale, tone: "amber" },
  finding_changed: {
    label: "Finding updated",
    icon: FileCheck2,
    tone: "neutral",
  },
  warning: { label: "Limitation", icon: TriangleAlert, tone: "amber" },
  answer: { label: "Your answer", icon: Check, tone: "green" },
  verdict: { label: "Conclusion", icon: ShieldCheck, tone: "green" },
};

const stages = [
  ["queued", "Audit job persisted"],
  ["reconstructing", "Evidence reconstructed"],
  ["reproducing", "Claim reproduced"],
  ["interrogating", "Scenario interrogated"],
  ["probing", "Mechanisms tested"],
  ["correcting", "Smallest repair evaluated"],
  ["complete", "Verdict composed"],
] as const;

const statusOrder = [
  "queued",
  "reconstructing",
  "reproducing",
  "interrogating",
  "waiting_for_user",
  "probing",
  "correcting",
  "composing",
  "complete",
];

function eventSummary(event: AuditEvent): string {
  const payload = event.payload;
  if (typeof payload.summary === "string") return payload.summary;
  if (typeof payload.observation === "string") return payload.observation;
  if (typeof payload.conclusion === "string") return payload.conclusion;
  if (typeof payload.message === "string") return payload.message;
  if (typeof payload.status === "string")
    return `Audit moved to ${payload.status.replaceAll("_", " ")}.`;
  if (typeof payload.tool === "string")
    return `${payload.tool} returned structured, provenance-linked results.`;
  if (
    payload.verdict &&
    typeof payload.verdict === "object" &&
    "summary" in payload.verdict
  )
    return String(payload.verdict.summary);
  if (typeof payload.mechanism === "string")
    return `${payload.mechanism.replaceAll("_", " ")} evidence changed this finding.`;
  return "Structured audit record saved.";
}

function Metric({
  label,
  value,
  accent,
}: {
  label: string;
  value: MetricValue | null;
  accent?: boolean;
}) {
  return (
    <div className={clsx("metric-cell", accent && "accent")}>
      <span>{label}</span>
      <strong>{value ? value.value.toFixed(3) : "—"}</strong>
      <small>{value?.protocol_id ?? "No protocol available"}</small>
      <code title={value?.provenance}>
        {value?.provenance ?? "not available"}
      </code>
    </div>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(finding.status === "confirmed");
  return (
    <article className={clsx("finding-card", finding.status)}>
      <button
        className="finding-head"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <span className={`finding-status ${finding.status}`}>
          {finding.status}
        </span>
        <span>
          <strong>{finding.mechanism.replaceAll("_", " ")}</strong>
          <small>{finding.features.join(", ") || "Protocol-level check"}</small>
        </span>
        <span className={`severity ${finding.severity}`}>
          {finding.severity}
        </span>
        <ChevronDown aria-hidden="true" />
      </button>
      {open && (
        <div className="finding-body">
          <p>{finding.conclusion}</p>
          <div
            className="finding-sources"
            aria-label="Finding evidence references"
          >
            {finding.evidence_ids.map((reference) => (
              <code key={reference}>{reference}</code>
            ))}
          </div>
          <div className="change-box">
            <HelpCircle aria-hidden="true" />
            <span>
              <strong>What would change this?</strong>
              {finding.what_would_change_this}
            </span>
          </div>
          <small>
            Confidence {(finding.confidence * 100).toFixed(0)}% ·{" "}
            {finding.evidence_ids.length} evidence record(s)
          </small>
        </div>
      )}
    </article>
  );
}

export function AuditWorkspace({
  audit,
  project,
  events,
  busy,
  report,
  onAnswer,
  onReport,
  onRestart,
}: Props) {
  const complete = audit.status === "complete";
  const interrupted = ["failed", "failed_partial"].includes(audit.status);
  const partial = audit.status === "failed_partial";
  const terminal = complete || interrupted;
  const waiting =
    audit.status === "waiting_for_user" && audit.open_questions.length > 0;
  const comparison = audit.metric_comparison;
  const currentOrder = statusOrder.indexOf(audit.status);
  const confirmed = audit.findings.filter(
    (finding) => finding.status === "confirmed",
  ).length;
  const cleared = audit.findings.filter(
    (finding) => finding.status === "cleared",
  ).length;
  const visibleEvents = useMemo(
    () =>
      events.filter((event) => event.type !== "finding_changed" || complete),
    [events, complete],
  );

  function downloadReport() {
    if (!report) return;
    const url = URL.createObjectURL(
      new Blob([report], { type: "text/markdown" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `polygraphml-${audit.audit_id}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="audit-shell enter" aria-labelledby="audit-title">
      <header className="audit-header">
        <div>
          <p className="eyebrow">
            {complete
              ? "State 7 · Verdict"
              : interrupted
                ? partial
                  ? "Partial result · Evidence preserved"
                  : "Audit interrupted"
                : waiting
                  ? "State 5 · Human checkpoint"
                  : "State 4 · Durable audit"}
          </p>
          <h1 id="audit-title">{project.name}</h1>
          <p className="audit-id">
            Audit <code>{audit.audit_id}</code> ·{" "}
            {audit.reproduction_tier?.replaceAll("_", " ") ??
              "reconstruction pending"}
          </p>
        </div>
        <div
          className={clsx(
            "status-chip",
            complete
              ? "good"
              : interrupted
                ? "danger"
                : waiting
                  ? "attention"
                  : "working",
          )}
        >
          {complete ? (
            <CheckCircle2 aria-hidden="true" />
          ) : interrupted ? (
            <TriangleAlert aria-hidden="true" />
          ) : waiting ? (
            <HelpCircle aria-hidden="true" />
          ) : (
            <Activity aria-hidden="true" />
          )}
          {audit.status.replaceAll("_", " ")}
        </div>
      </header>

      {!terminal && (
        <div className="durability-note" role="status">
          <Clock3 aria-hidden="true" />
          <span>
            <strong>Your audit runs independently of this tab.</strong>{" "}
            Refreshing reconnects to event {audit.last_event_sequence}.
          </span>
        </div>
      )}

      {interrupted && (
        <div className="audit-interruption" role="alert">
          <TriangleAlert aria-hidden="true" />
          <span>
            <strong>
              {partial
                ? "The audit stopped after collecting partial evidence."
                : "The audit could not complete."}
            </strong>{" "}
            Persisted events and computed results remain visible; no missing
            check is treated as cleared.
          </span>
          <button className="button ghost" onClick={onRestart}>
            <RotateCcw aria-hidden="true" /> Start a new audit
          </button>
        </div>
      )}

      <div className="audit-grid">
        <aside className="audit-rail">
          <p className="panel-label">Execution plan</p>
          <ol className="stage-list">
            {stages.map(([status, label]) => {
              const order = statusOrder.indexOf(status);
              const done =
                complete ||
                order < currentOrder ||
                (audit.status === "waiting_for_user" &&
                  order <= statusOrder.indexOf("interrogating"));
              const active =
                !terminal &&
                (audit.status === status ||
                  (audit.status === "waiting_for_user" &&
                    status === "interrogating"));
              return (
                <li
                  key={status}
                  className={clsx(done && "done", active && "active")}
                >
                  <span>
                    {done ? (
                      <Check aria-hidden="true" />
                    ) : active ? (
                      <CircleDot aria-hidden="true" />
                    ) : null}
                  </span>
                  <div>
                    {label}
                    {active && !interrupted && (
                      <small>
                        {waiting ? "Needs your context" : "Running now"}
                      </small>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
          <div className="rail-meta">
            <span>Evidence source</span>
            <strong>{project.source.type}</strong>
            {project.source.resolved_commit && (
              <code>{project.source.resolved_commit.slice(0, 10)}…</code>
            )}
            <span>Evaluator model</span>
            <strong>{audit.provenance.agent_model}</strong>
            <span>Seed</span>
            <strong>{audit.provenance.random_seed}</strong>
          </div>
        </aside>

        <div className="trace-column">
          <div className="trace-heading">
            <div>
              <p className="panel-label">Decision Trace</p>
              <h2>
                {complete
                  ? "How the verdict was earned"
                  : "What PolygraphML is establishing"}
              </h2>
            </div>
            <span>{events.length} signed events</span>
          </div>

          {visibleEvents.length === 0 && (
            <div className="trace-empty">
              <Activity aria-hidden="true" />
              <p>Waiting for the first durable worker event…</p>
            </div>
          )}
          <ol className="trace-list" aria-live="polite">
            {visibleEvents.map((event) => {
              const meta = eventMeta[event.type] ?? eventMeta.audit_state!;
              const Icon = meta.icon;
              return (
                <li key={event.event_id} className={`trace-event ${meta.tone}`}>
                  <div className="trace-node">
                    <Icon aria-hidden="true" />
                  </div>
                  <article>
                    <header>
                      <span>{meta.label}</span>
                      <span>
                        #{event.sequence} · {event.actor}
                      </span>
                    </header>
                    <p>{eventSummary(event)}</p>
                    {event.provenance_refs.length > 0 && (
                      <footer>
                        {event.provenance_refs.slice(0, 3).map((ref) => (
                          <code key={ref}>{ref}</code>
                        ))}
                      </footer>
                    )}
                  </article>
                </li>
              );
            })}
          </ol>

          {waiting && (
            <QuestionCard
              question={audit.open_questions[0]!}
              busy={busy}
              onAnswer={onAnswer}
            />
          )}

          {comparison?.corrected && (
            <section
              className={clsx("comparison-card", complete && "complete")}
              aria-labelledby="comparison-title"
            >
              <div className="comparison-head">
                <div>
                  <p className="eyebrow">
                    State 6 · Smallest justified correction
                  </p>
                  <h2 id="comparison-title">
                    The score changes when timing is respected.
                  </h2>
                </div>
                <Scale aria-hidden="true" />
              </div>
              <div className="metric-grid">
                <Metric label="Reported" value={comparison.reported} />
                <Metric label="Reproduced" value={comparison.reproduced} />
                <div className="metric-arrow">
                  <ArrowDown aria-hidden="true" />
                </div>
                <Metric label="Corrected" value={comparison.corrected} accent />
              </div>
              {comparison.corrected && comparison.reproduced && (
                <p className="metric-delta">
                  <strong>
                    {(
                      (comparison.reproduced.value -
                        comparison.corrected.value) *
                      100
                    ).toFixed(1)}
                  </strong>{" "}
                  AUC points of measured inflation after removing the
                  unavailable feature.
                </p>
              )}
            </section>
          )}

          {complete && audit.verdict && (
            <section className="verdict-card" aria-labelledby="verdict-title">
              <div className="verdict-mark">
                <ShieldCheck aria-hidden="true" />
              </div>
              <div>
                <p className="eyebrow">Evidence-backed verdict</p>
                <h2 id="verdict-title">
                  {audit.verdict.trust_state.replaceAll("_", " ")}
                </h2>
                <p>{audit.verdict.summary}</p>
                <div className="verdict-counts">
                  <span>
                    <strong>{confirmed}</strong> confirmed
                  </span>
                  <span>
                    <strong>{cleared}</strong> cleared
                  </span>
                  <span>
                    <strong>{audit.verdict.unsupported_checks.length}</strong>{" "}
                    limitation
                  </span>
                </div>
              </div>
            </section>
          )}

          {audit.findings.length > 0 && (
            <section className="findings-section">
              <div className="trace-heading">
                <div>
                  <p className="panel-label">Findings</p>
                  <h2>Claims, evidence, and falsifiers</h2>
                </div>
              </div>
              {audit.findings.map((finding) => (
                <FindingCard
                  key={`${finding.finding_id}:${finding.status}`}
                  finding={finding}
                />
              ))}
            </section>
          )}

          {complete && (
            <div className="result-actions">
              <button
                className="button primary"
                disabled={busy}
                onClick={onReport}
              >
                {busy
                  ? "Generating…"
                  : report
                    ? "Report ready"
                    : "Generate stakeholder report"}
                <FileCheck2 aria-hidden="true" />
              </button>
              <button
                className="button secondary"
                disabled={!report}
                onClick={downloadReport}
              >
                <Download aria-hidden="true" /> Download Markdown
              </button>
              <button className="button ghost" onClick={onRestart}>
                <RotateCcw aria-hidden="true" /> Run another audit
              </button>
            </div>
          )}
          {report && (
            <section className="report-preview">
              <p className="panel-label">Generated technical report</p>
              <pre tabIndex={0} aria-label="Technical report content">
                {report}
              </pre>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}

function QuestionCard({
  question,
  busy,
  onAnswer,
}: {
  question: Question;
  busy: boolean;
  onAnswer: (question: Question, answer: string) => void;
}) {
  return (
    <section className="question-card" aria-labelledby="question-title">
      <div className="question-icon">
        <HelpCircle aria-hidden="true" />
      </div>
      <div>
        <p className="eyebrow">Your context can change this conclusion</p>
        <h2 id="question-title">{question.text}</h2>
        <p>{question.why_it_matters}</p>
        <div className="answer-row">
          {question.options.map((option) => (
            <button
              key={option}
              className={clsx(
                "answer-button",
                option === "after" && "recommended",
              )}
              disabled={busy}
              onClick={() => onAnswer(question, option)}
            >
              <span>
                {option === "after"
                  ? "Only after the call"
                  : option === "before"
                    ? "Available before selection"
                    : "Not sure"}
              </span>
              {option === "after" && (
                <small>Matches this benchmark scenario</small>
              )}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
