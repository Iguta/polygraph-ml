import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function confirmEvidenceAndScenario(page: Page) {
  await expect(
    page.getByRole("heading", { name: /pieces of the claim/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: /confirm evidence map/i }).click();
  await expect(
    page.getByRole("heading", { name: /when this prediction has to be true/i }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /start evidence-backed audit/i })
    .click();
}

test("flagship audit proves fallback, replay, correction, reports, and repair", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /earned its score/i }),
  ).toBeVisible();
  await expect(
    page.getByText(/audit service ready · fixture configured/i),
  ).toBeVisible();
  const landingAccessibility = await new AxeBuilder({ page }).analyze();
  expect(landingAccessibility.violations).toEqual([]);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: /polygraphml home/i }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Docs" })).toBeFocused();

  await page.getByRole("button", { name: /run the flagship audit/i }).click();
  await expect(page.getByText(/4 artifacts verified/i)).toBeVisible();
  await page.getByRole("button", { name: /confirm evidence map/i }).click();
  await expect(page.getByLabel(/at what moment/i)).toHaveValue(
    /before the current marketing call/i,
  );

  let rejectedStreams = 0;
  await page.route("**/api/v1/audits/*/events**", async (route) => {
    if (route.request().headers().accept?.includes("text/event-stream")) {
      rejectedStreams += 1;
      await route.abort("connectionfailed");
      return;
    }
    await route.continue();
  });
  await page
    .getByRole("button", { name: /start evidence-backed audit/i })
    .click();

  await expect(
    page.getByRole("heading", {
      name: /uci bank marketing current-call duration/i,
    }),
  ).toBeVisible();
  await expect(page.getByText(/transport: polling fallback/i)).toBeVisible({
    timeout: 15_000,
  });
  expect(rejectedStreams).toBeGreaterThanOrEqual(3);
  await page.unroute("**/api/v1/audits/*/events**");

  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: /uci bank marketing current-call duration/i,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /is duration available/i }),
  ).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: /only after the event/i }).click();

  await expect(
    page.getByRole("heading", { name: "materially inflated" }),
  ).toBeVisible({ timeout: 60_000 });
  await expect(
    page.getByText(/state 6 · smallest justified correction/i),
  ).toBeVisible();
  await expect(page.getByText("0.871")).toHaveCount(2);
  await expect(page.getByText("0.733")).toBeVisible();
  await expect(page.getByText(/post outcome/i).first()).toBeVisible();
  await expect(page.getByText(/what would change this/i).first()).toBeVisible();
  await expect(page.getByText(/fixture · no live model call/i)).toBeVisible();

  await page.getByRole("button", { name: /generate executive brief/i }).click();
  await expect(page.getByText(/generated executive report/i)).toBeVisible();
  await page
    .getByRole("button", { name: /generate technical report/i })
    .click();
  await expect(page.getByText(/generated technical report/i)).toBeVisible();

  await page
    .getByRole("button", { name: /build deterministic repair/i })
    .click();
  await expect(page.getByText(/deterministic repair is ready/i)).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /download repair bundle/i }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/polygraphml-.*-repair\.zip/);

  const verdictAccessibility = await new AxeBuilder({ page }).analyze();
  expect(verdictAccessibility.violations).toEqual([]);
});

test("public clean control completes without a false confirmation", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: /run public uci covid clean control/i })
    .click();
  await expect(page.getByText(/3 artifacts verified/i)).toBeVisible();
  await confirmEvidenceAndScenario(page);

  await expect(
    page.getByRole("heading", { name: /is .* available/i }),
  ).toBeVisible({ timeout: 30_000 });
  await page
    .getByRole("button", { name: /available before the decision/i })
    .click();

  await expect(page.getByText(/^0 confirmed$/i)).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText(/^4 cleared$/i)).toBeVisible();
});

test("live badge appears only from stored OpenAI execution provenance", async ({
  page,
}) => {
  const now = "2026-07-21T00:00:00Z";
  const scenario = {
    revision: 1,
    target_definition: "A test outcome",
    row_entity: "One row",
    decision_time: "Before the decision",
    prediction_horizon: "One day",
    split_unit: "row_id",
    intended_metric: "roc_auc",
    positive_label: "1",
    notes: "",
  };
  const project = {
    project_id: "prj_live",
    session_id: "ses_live",
    name: "Recorded live audit",
    source: { type: "benchmark", benchmark_id: "mock_live" },
    status: "ready",
    artifact_ids: [],
    mapping: {},
    scenarios: [scenario],
    feature_context: {},
    warnings: [],
    created_at: now,
    updated_at: now,
    artifacts: [],
  };
  const audit = {
    audit_id: "aud_live",
    project_id: "prj_live",
    session_id: "ses_live",
    scenario_revision: 1,
    mode: "complete_audit",
    status: "complete",
    reproduction_tier: "static_only",
    hypothesis_ids: [],
    evidence_ids: [],
    finding_ids: [],
    correction_ids: [],
    question_ids: [],
    metric_comparison: null,
    verdict: {
      trust_state: "supported",
      summary:
        "No tested mechanism was confirmed in this UI provenance fixture.",
      finding_counts: {},
      unsupported_checks: [],
    },
    provenance: {
      source_commit: null,
      artifact_hashes: [],
      evaluator_version: "0.2.0",
      agent_model: "gpt-5.6-sol",
      prompt_schema_version: "audit-v2",
      random_seed: 42,
      package_versions: {},
      split_hash: null,
      feature_order: [],
      agent_execution: {
        provider: "openai",
        mode: "live",
        requested_model: "gpt-5.6-sol",
        resolved_model: "gpt-5.6-sol",
        reasoning_effort: "high",
        harness_version: "audit-v2",
        input_tokens: 10,
        output_tokens: 5,
        total_tokens: 15,
        latency_ms: 20,
        trace_id: "trace_mock",
      },
      compute_execution: null,
    },
    last_event_sequence: 0,
    checkpoint: "complete",
    lease_owner: null,
    lease_expires_at: null,
    created_at: now,
    updated_at: now,
    findings: [],
    open_questions: [],
    events_url: "/api/v1/audits/aud_live/events",
  };
  await page.addInitScript(() => {
    sessionStorage.setItem("polygraphml.session", "mock-token");
    sessionStorage.setItem("polygraphml.active-audit", "aud_live");
    sessionStorage.setItem("polygraphml.active-project", "prj_live");
  });
  await page.route("**/api/v1/projects/prj_live", (route) =>
    route.fulfill({ json: { data: project, error: null } }),
  );
  await page.route("**/api/v1/audits/aud_live", (route) =>
    route.fulfill({ json: { data: audit, error: null } }),
  );
  await page.route("**/api/v1/audits/aud_live/events**", (route) =>
    route.fulfill({ json: { data: [], error: null } }),
  );

  await page.goto("/");
  await expect(page.getByText(/live · gpt-5\.6-sol/i)).toBeVisible();
  await expect(page.getByText(/fixture · no live model call/i)).toHaveCount(0);
});

for (const viewport of [
  { label: "mobile", width: 390, height: 844 },
  { label: "laptop", width: 1366, height: 768 },
  { label: "1080p recording", width: 1920, height: 1080 },
]) {
  test(`intake remains usable at ${viewport.label} size`, async ({ page }) => {
    await page.setViewportSize({
      width: viewport.width,
      height: viewport.height,
    });
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /earned its score/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /run the flagship audit/i }),
    ).toBeVisible();
    const horizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(horizontalOverflow).toBeLessThanOrEqual(1);
  });
}
