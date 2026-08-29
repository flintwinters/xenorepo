import { expect, test } from "@xenorepo/browser-testing";

test("[acceptance] operator navigates repository evidence and records a baseline", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/");
  await expect(page.locator("#app")).toContainText("Repository scorecard", {
    timeout: 30_000,
  });
  await expect(page.locator("#app")).toContainText("source lines");
  await expect(page.locator("#app")).toContainText("Lines by language");
  await expect(page.locator("nav .x-ui-command").first()).toContainText("overview");

  await page.getByRole("button", { name: "modules", exact: true }).click();
  await expect(page.locator("#app")).toContainText("Monotools modules");
  await expect(page.locator("#app")).toContainText("audit");
  await expect(page.locator(".module-table")).toContainText("Measure architecture and structural invariants");
  await expect(page.locator(".module-table")).toBeVisible();
  const widths = await page.locator(".module-table th").evaluateAll((headers) => Object.fromEntries(
    headers.map((header) => [header.textContent?.trim(), header.getBoundingClientRect().width]),
  ));
  expect(widths.Description).toBeGreaterThan(widths.Lines * 2);
  expect(widths.Explanation).toBeGreaterThan(widths.Apps * 2);

  await page.getByRole("button", { name: "explorer", exact: true }).click();
  await expect(page.locator("#app")).toContainText("Repository explorer");
  await expect(page.locator(".tree-row").first()).toContainText("xenorepo");
  await expect(page.locator(".tree-lines").first()).toHaveText(/^\d[\d,]*L$/);
  await expect(page.locator(".tree-bytes").first()).toHaveText(/^\d+(?:B|KB|MB|GB|TB)$/);
  const metadataLayout = await page.locator(".tree-row").evaluateAll((rows) => rows.slice(0, 8).map((row) => {
    const lines = row.querySelector<HTMLElement>(".tree-lines");
    const bytes = row.querySelector<HTMLElement>(".tree-bytes");
    const name = row.querySelector<HTMLElement>("span");
    return { order: [lines, bytes, name].map((element) => element?.getBoundingClientRect().left),
      height: row.getBoundingClientRect().height,
      border: getComputedStyle(row).borderBottomWidth,
      font: lines ? getComputedStyle(lines).fontFamily : "" };
  }));
  expect(metadataLayout.every((item) => item.order[0]! < item.order[1]! &&
    item.order[1]! < item.order[2]!)).toBe(true);
  expect(metadataLayout.every((item) => item.height <= 13 && item.border === "0px")).toBe(true);
  expect(metadataLayout.every((item) => item.font.includes("Courier New"))).toBe(true);

  await page.getByRole("button", { name: "architecture", exact: true }).click();
  await expect(page.locator("#app")).toContainText("High-level architecture");
  await expect(page.locator("#app")).toContainText("FastAPI + dist");

  await page.getByRole("button", { name: "RECORD SNAPSHOT", exact: true }).click();
  await expect(page.locator("#app")).toContainText("Repository trajectory");
  await expect(page.locator("#app")).toContainText(/Snapshot recorded|already recorded/);
});

test("[visual] initial repository cockpit", async ({ page }) => {
  await page.goto("/");
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("repository-cockpit.png", {
    mask: [page.locator("time")],
    maxDiffPixels: 300,
  });
});
