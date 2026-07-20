import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Scenario } from "../types";
import { ScenarioForm } from "./ScenarioForm";

const scenario: Scenario = {
  revision: 1,
  target_definition: "Customer churns within 30 days",
  row_entity: "One customer snapshot",
  decision_time: "Before campaign selection",
  prediction_horizon: "30 days",
  split_unit: "customer_id",
  intended_metric: "roc_auc",
  positive_label: "1",
  notes: "",
};

describe("ScenarioForm", () => {
  it("explains why timing matters and submits the declared scenario", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    render(<ScenarioForm initial={scenario} busy={false} onSubmit={submit} />);
    expect(
      screen.getByText(/same feature can be valid or leakage/i),
    ).toBeVisible();
    expect(screen.getByLabelText(/at what moment/i)).toHaveValue(
      "Before campaign selection",
    );
    await user.click(
      screen.getByRole("button", { name: /start evidence-backed audit/i }),
    );
    expect(submit).toHaveBeenCalledWith(scenario);
  });
});
