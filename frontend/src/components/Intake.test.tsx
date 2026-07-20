import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Intake } from "./Intake";

describe("Intake", () => {
  it("presents the three honest intake paths and starts the benchmark", async () => {
    const user = userEvent.setup();
    const benchmark = vi.fn();
    render(
      <Intake
        busy={false}
        onBenchmark={benchmark}
        onPublicBenchmark={vi.fn()}
        onGithub={vi.fn()}
        onUpload={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("heading", { name: /earned its score/i }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: /audit from github/i }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: /upload model evidence/i }),
    ).toBeVisible();
    expect(screen.getByText(/pickle files are rejected/i)).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: /run the guided benchmark/i }),
    );
    expect(benchmark).toHaveBeenCalledOnce();
  });

  it("submits the repository URL and immutable-ref candidate", async () => {
    const user = userEvent.setup();
    const github = vi.fn();
    render(
      <Intake
        busy={false}
        onBenchmark={vi.fn()}
        onPublicBenchmark={vi.fn()}
        onGithub={github}
        onUpload={vi.fn()}
      />,
    );
    await user.type(
      screen.getByRole("textbox", { name: /repository url/i }),
      "https://github.com/openai/openai-python",
    );
    await user.clear(
      screen.getByRole("textbox", { name: /branch, tag, or commit/i }),
    );
    await user.type(
      screen.getByRole("textbox", { name: /branch, tag, or commit/i }),
      "v1.0.0",
    );
    await user.click(
      screen.getByRole("button", { name: /inspect repository/i }),
    );
    expect(github).toHaveBeenCalledWith(
      "https://github.com/openai/openai-python",
      "v1.0.0",
    );
  });
});
