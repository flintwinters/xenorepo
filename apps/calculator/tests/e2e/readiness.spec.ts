import { type Page } from "@playwright/test";
import { expect, test } from "@xenorepo/browser-testing";

const display = (page: Page) => page.getByLabel("Calculator display");

async function press(page: Page, ...names: string[]) {
  for (const name of names) await page.getByRole("button", { name, exact: true }).click();
}

test("[acceptance] button input completes and clears ordinary arithmetic", async ({ page }) => {
  await page.goto("/");
  await expect(display(page)).toHaveText("0");
  await press(page, "1", "2", "Decimal point", "5", "Add", "7", "Decimal point", "5", "Equals");
  await expect(display(page)).toHaveText("20");
  await press(page, "All clear", "2", "Multiply", "3", "Add", "4", "Equals");
  await expect(display(page)).toHaveText("10");
  await press(page, "All clear", "5", "0", "Percent");
  await expect(display(page)).toHaveText("0.5");
  await press(page, "Change sign");
  await expect(display(page)).toHaveText("-0.5");
  await press(page, "All clear", "0", "0", "7");
  await expect(display(page)).toHaveText("7");
});

test("[acceptance] errors and reloads recover to a clean stateless value", async ({ page }) => {
  await page.goto("/");
  await press(page, "8", "Divide", "0", "Equals");
  await expect(display(page)).toHaveText("Error");
  await press(page, "3");
  await expect(display(page)).toHaveText("3");
  await page.keyboard.press("9");
  await expect(display(page)).toHaveText("3");
  await page.reload();
  await expect(display(page)).toHaveText("0");
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length })))
    .toEqual({ local: 0, session: 0 });
});

test("[visual] complete calculator at rest", async ({ page }) => {
  await page.goto("/");
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("calculator.png", { maxDiffPixels: 200 });
});
