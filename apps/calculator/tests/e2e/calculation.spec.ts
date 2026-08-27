import { expect, test } from "@xenorepo/browser-testing";

test("[acceptance] button input calculates a chained decimal expression", async ({ page }) => {
  await page.goto("/");
  const output = page.getByLabel("Display");
  await expect(output).toHaveText("0");

  for (const name of ["1", "2", ".", "5", "Multiply", "4", "Add", "2", "Equals"])
    await page.getByRole("button", { name, exact:true }).click();

  await expect(output).toHaveText("52");
  await expect(page.getByText("50 + 2 =", { exact:true })).toBeVisible();
});

test("[acceptance] keyboard, correction, percent, sign, and error recovery work", async ({ page }) => {
  await page.goto("/");
  const output = page.getByLabel("Display");

  await page.keyboard.type("123");
  await page.keyboard.press("Backspace");
  await page.keyboard.type("+25%");
  await page.keyboard.press("Enter");
  await expect(output).toHaveText("12.25");

  await page.getByRole("button", { name:"Change sign" }).click();
  await expect(output).toHaveText("-12.25");
  await page.keyboard.press("Escape");
  await page.keyboard.type("8/0");
  await page.keyboard.press("Enter");
  await expect(output).toHaveText("Error");
  await page.keyboard.press("7");
  await expect(output).toHaveText("7");
});
