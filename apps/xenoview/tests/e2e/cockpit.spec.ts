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

  await expect(page.getByRole("button", { name: "modules", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "explorer", exact: true }).click();
  await expect(page.locator("#app")).toContainText("Repository explorer");
  await expect(page.locator("#app")).toContainText("Files and semantic Monotools modules");
  await expect(page.locator("#app")).toContainText("audit");
  await expect(page.locator(".explorer-table")).toContainText("Measure architecture and structural invariants");
  await expect(page.locator(".explorer-table")).toBeVisible();
  await expect(page.locator(".page table")).toHaveCount(1);
  const widths = await page.locator(".explorer-table th").evaluateAll((headers) => Object.fromEntries(
    headers.map((header) => [header.textContent?.trim(), header.getBoundingClientRect().width]),
  ));
  expect(widths.Description).toBeGreaterThan(widths.Definitions * 2);
  expect(widths.Explanation).toBeGreaterThan(widths.Apps * 2);

  await expect(page.locator(".tree-row").first()).toContainText("xenorepo");
  await expect(page.locator(".tree-entry").first()).toHaveAttribute("data-lines", /^\d[\d,]*L$/);
  await expect(page.locator(".tree-entry").first()).toHaveAttribute("data-bytes", /^\d+(?:B|KB|MB|GB|TB)$/);
  const metadataLayout = await page.locator(".tree-row").evaluateAll((rows) => rows.slice(0, 8).map((row) => {
    const entry = row.querySelector<HTMLElement>(".tree-entry");
    return { lines: entry?.dataset.lines, bytes: entry?.dataset.bytes,
      height: row.getBoundingClientRect().height,
      border: getComputedStyle(row).borderBottomWidth,
      font: entry ? getComputedStyle(entry, "::after").fontFamily : "" };
  }));
  expect(metadataLayout.every((item) => /^\d[\d,]*L$/.test(item.lines ?? "") &&
    /^\d+(?:B|KB|MB|GB|TB)$/.test(item.bytes ?? ""))).toBe(true);
  expect(metadataLayout.every((item) => item.height <= 14 && item.border === "0px")).toBe(true);
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
