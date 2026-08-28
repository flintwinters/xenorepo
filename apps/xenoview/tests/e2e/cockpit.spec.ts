import { test, expect } from "@playwright/test";

test("operator navigates repository evidence and records a baseline", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Repository scorecard");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("source lines");

  await page.getByText("modules", { exact: true }).click();
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Monotools modules");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("audit");

  await page.getByText("architecture", { exact: true }).click();
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("High-level architecture");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Central Lit UI");

  await page.getByText("RECORD SNAPSHOT", { exact: true }).click();
  await expect(page.locator("x-xenorepo-cockpit")).toContainText("Repository trajectory");
  await expect(page.locator("x-xenorepo-cockpit")).toContainText(/Snapshot recorded|already recorded/);
});
