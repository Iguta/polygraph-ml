import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("benchmark reaches a provenance-backed fixture verdict and survives refresh", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /earned its score/i }),
  ).toBeVisible();
  await expect(
    page.getByText(/fixture audit · no live model call/i),
  ).toBeVisible();
  const landingAccessibility = await new AxeBuilder({ page }).analyze();
  expect(landingAccessibility.violations).toEqual([]);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: /polygraphml home/i }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Docs" })).toBeFocused();

  await page.getByRole("button", { name: /run the guided benchmark/i }).click();
  await expect(
    page.getByRole("heading", { name: /pieces of the claim/i }),
  ).toBeVisible();
  await expect(page.getByText(/3 artifacts verified/i)).toBeVisible();
  await page.getByRole("button", { name: /confirm evidence map/i }).click();

  await expect(
    page.getByRole("heading", { name: /when this prediction has to be true/i }),
  ).toBeVisible();
  await expect(page.getByLabel(/at what moment/i)).toHaveValue(
    /before the campaign/i,
  );
  await page
    .getByRole("button", { name: /start evidence-backed audit/i })
    .click();

  await expect(
    page.getByRole("heading", { name: /campaign timing benchmark/i }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: /campaign timing benchmark/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /is call_duration available/i }),
  ).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /only after the call/i }).click();

  await expect(
    page.getByRole("heading", { name: "materially inflated" }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByText(/state 6 · smallest justified correction/i),
  ).toBeVisible();
  await expect(page.getByText("0.863")).toBeVisible();
  await expect(page.getByText(/post outcome/i).first()).toBeVisible();
  await expect(page.getByText(/what would change this/i).first()).toBeVisible();

  await page
    .getByRole("button", { name: /generate stakeholder report/i })
    .click();
  await expect(page.getByText(/generated technical report/i)).toBeVisible();
  const verdictAccessibility = await new AxeBuilder({ page }).analyze();
  expect(verdictAccessibility.violations).toEqual([]);
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
      page.getByRole("button", { name: /run the guided benchmark/i }),
    ).toBeVisible();
    const horizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(horizontalOverflow).toBeLessThanOrEqual(1);
  });
}
