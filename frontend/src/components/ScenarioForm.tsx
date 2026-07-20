import { useState, type FormEvent } from "react";
import { ArrowRight, Clock3, Info, ScanSearch } from "lucide-react";

import type { Scenario } from "../types";

interface Props {
  initial: Scenario;
  busy: boolean;
  onSubmit: (scenario: Scenario) => void;
}

export function ScenarioForm({ initial, busy, onSubmit }: Props) {
  const [scenario, setScenario] = useState(initial);
  const update = (key: keyof Scenario, value: string) =>
    setScenario({ ...scenario, [key]: value });

  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit(scenario);
  }

  return (
    <section
      className="workspace narrow enter"
      aria-labelledby="scenario-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">State 3 · Prediction contract</p>
          <h1 id="scenario-title">
            Tell us when this prediction has to be true.
          </h1>
        </div>
        <div className="scenario-mark">
          <Clock3 aria-hidden="true" />
        </div>
      </div>
      <div className="notice info">
        <Info aria-hidden="true" />
        <span>
          The same feature can be valid or leakage depending on{" "}
          <strong>when</strong> the prediction is made.
        </span>
      </div>
      <form className="scenario-form" onSubmit={submit}>
        <label className="full">
          What outcome is predicted?
          <span>Be precise about the label and outcome window.</span>
          <textarea
            required
            value={scenario.target_definition}
            onChange={(event) =>
              update("target_definition", event.target.value)
            }
          />
        </label>
        <label>
          What does one row represent?
          <input
            required
            value={scenario.row_entity}
            onChange={(event) => update("row_entity", event.target.value)}
          />
        </label>
        <label>
          Prediction horizon
          <input
            required
            value={scenario.prediction_horizon}
            onChange={(event) =>
              update("prediction_horizon", event.target.value)
            }
          />
        </label>
        <label className="full emphasis-field">
          At what moment must the prediction be available?
          <span>
            Features created after this moment may invalidate the score.
          </span>
          <textarea
            required
            value={scenario.decision_time}
            onChange={(event) => update("decision_time", event.target.value)}
          />
        </label>
        <label>
          Entity that must not cross splits
          <input
            required
            value={scenario.split_unit}
            onChange={(event) => update("split_unit", event.target.value)}
          />
        </label>
        <label>
          Success metric
          <select
            value={scenario.intended_metric}
            onChange={(event) => update("intended_metric", event.target.value)}
          >
            <option value="roc_auc">ROC AUC</option>
            <option value="accuracy">Accuracy</option>
            <option value="f1">F1</option>
          </select>
        </label>
        <label className="full">
          Notes for the auditor
          <span>Optional operational context, exclusions, or constraints.</span>
          <textarea
            value={scenario.notes}
            onChange={(event) => update("notes", event.target.value)}
          />
        </label>
        <div className="form-footer">
          <div>
            <ScanSearch aria-hidden="true" />
            <span>
              PolygraphML will reproduce the claim before asking the model to
              investigate it.
            </span>
          </div>
          <button className="button primary" disabled={busy} type="submit">
            {busy ? "Creating audit…" : "Start evidence-backed audit"}
            <ArrowRight aria-hidden="true" />
          </button>
        </div>
      </form>
    </section>
  );
}
