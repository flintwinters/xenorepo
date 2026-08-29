import { expect, test } from "@xenorepo/browser-testing";

test("[acceptance] keyboard flow completes and restarts the inventory", async ({ page }) => {
  await page.goto("/");
  for (let item = 0; item < 8; item += 1) {
    await page.keyboard.press("5");
    await page.keyboard.press("Enter");
  }
  await expect(page.getByText("PROFILE COMPLETE")).toBeVisible();
  await page.keyboard.press("r");
  await expect(page.getByText("ITEM 1 / 8")).toBeVisible();
});

test("[visual] initial working-style inventory", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("ITEM 1 / 8")).toBeVisible();
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("working-style-inventory.png", { maxDiffPixels: 300 });
});
