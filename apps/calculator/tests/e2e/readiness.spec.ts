import { acknowledgeHttpFailures, expect, test } from "@xenorepo/browser-testing";

test("[acceptance] MonoForm submits arithmetic to the authoritative server", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Left operand").fill("12.5");
  await page.getByLabel("Operator").selectOption("add");
  await page.getByLabel("Right operand").fill("7.5");
  const request = page.waitForRequest((value) => value.url().endsWith("/api/calculate"));
  await page.getByRole("button", { name: "CALCULATE" }).click();
  expect((await request).postDataJSON()).toEqual({
    left_operand: 12.5, operator: "add", right_operand: 7.5,
  });
  await expect(page.getByRole("status")).toContainText('"result":20');
});

test("[acceptance] server validation marks division by zero and reload clears the result", async ({ page }) => {
  acknowledgeHttpFailures(page, [422]);
  await page.goto("/");
  await page.getByLabel("Left operand").fill("8");
  await page.getByLabel("Operator").selectOption("divide");
  await page.getByLabel("Right operand").fill("0");
  await page.getByRole("button", { name: "CALCULATE" }).click();
  await expect(page.getByText("Division by zero is undefined.")).toBeVisible();
  await expect(page.getByLabel("Right operand")).toHaveAttribute("aria-invalid", "true");
  await page.reload();
  await expect(page.getByRole("status")).toBeEmpty();
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length })))
    .toEqual({ local: 0, session: 0 });
});

test("[acceptance] calculator rejects cross-origin mutation", async ({ page }) => {
  acknowledgeHttpFailures(page, [403]);
  await page.goto("/");
  const response = await page.request.post("/api/calculate", {
    headers: { origin: "https://example.test" },
    data: { left_operand: 1, operator: "add", right_operand: 2 },
  });
  expect(response.status()).toBe(403);
});

test("[visual] generated calculator form", async ({ page }) => {
  await page.goto("/");
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("calculator.png", { maxDiffPixels: 200 });
});
