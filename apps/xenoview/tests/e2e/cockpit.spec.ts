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

  await page.getByRole("button", { name: "explorer", exact: true }).click();
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Repository explorer");
  await expect(page.locator(".tree-row").first()).toContainText("xenorepo");

  await page.getByRole("button", { name: "architecture", exact: true }).click();
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("High-level architecture");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Central Lit UI");

  await page.getByRole("button", { name: "RECORD SNAPSHOT", exact: true }).click();
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Repository trajectory");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText(/Snapshot recorded|already recorded/);
});
