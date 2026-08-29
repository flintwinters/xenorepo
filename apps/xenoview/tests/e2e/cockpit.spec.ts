import { expect, test } from "@xenorepo/browser-testing";

test("[acceptance] operator navigates repository evidence and records a baseline", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Repository scorecard", {
    timeout: 30_000,
  });
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("source lines");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Lines by language");
  await expect(page.locator("nav x-command-button").first()).toContainText("overview");

  await page.getByRole("button", { name: "modules", exact: true }).click();
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Monotools modules");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("audit");
  await expect(page.locator(".module-table")).toContainText("Measure architecture and structural invariants");
  await expect(page.locator(".module-table")).toBeVisible();
  const widths = await page.locator(".module-table th").evaluateAll((headers) => Object.fromEntries(
    headers.map((header) => [header.textContent?.trim(), header.getBoundingClientRect().width]),
  ));
  expect(widths.Description).toBeGreaterThan(widths.Lines * 2);
  expect(widths.Explanation).toBeGreaterThan(widths.Apps * 2);

  await page.getByRole("button", { name: "explorer", exact: true }).click();
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Repository explorer");
  await expect(page.locator(".tree-row").first()).toContainText("xenorepo");

  await page.getByRole("button", { name: "architecture", exact: true }).click();
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("High-level architecture");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("FastAPI + dist");

  await page.getByRole("button", { name: "RECORD SNAPSHOT", exact: true }).click();
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Repository trajectory");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText(/Snapshot recorded|already recorded/);
});

test("[visual] initial repository cockpit", async ({ page }) => {
  await page.goto("/");
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("repository-cockpit.png", {
    mask: [page.locator("time")],
    maxDiffPixels: 300,
  });
});
