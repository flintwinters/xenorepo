const { expect, test } = require("@playwright/test");

test("creates and manages independent terminal windows", async ({ page }) => {
  await page.route("https://cdn.jsdelivr.net/**", route => route.abort());
  await page.goto("/");

  const state = await page.evaluate(() => {
    const desktop = document.querySelector("worminal-desktop");
    desktop.receive({ type: "ready", version: "3.13.2" });
    return [desktop.runtimePhase, desktop.runtimeMessage];
  });
  expect(state).toEqual(["ready", "PYTHON READY"]);
  await expect(page.getByText("WORMINAL", { exact: true })).toBeVisible();
  await expect(page.getByText("PYTHON READY", { exact: true })).toBeVisible();
  const first = page.getByLabel("python-1 command");
  await first.fill("6 * 7");
  await first.press("Enter");
  await page.evaluate(() => document.querySelector("worminal-desktop").receive({ type: "result", id: 1, value: "42" }));
  await expect(page.getByLabel("python-1 output")).toContainText("42");

  await page.getByRole("button", { name: "+ NEW TERMINAL" }).click();
  await expect(page.getByLabel("python-2 command")).toBeVisible();
  await page.getByRole("button", { name: "Minimize python-2" }).click();
  await expect(page.getByLabel("python-2 command")).toBeHidden();
  await page.getByRole("button", { name: "python-2" }).click();
  await expect(page.getByLabel("python-2 command")).toBeVisible();
  await page.getByRole("button", { name: "Maximize python-2" }).click();
  await expect(page.getByRole("region", { name: "python-2" })).toHaveClass(/maximized/);
  await page.getByRole("button", { name: "Close python-2" }).click();
  await expect(page.getByLabel("python-2 command")).toHaveCount(0);
});
