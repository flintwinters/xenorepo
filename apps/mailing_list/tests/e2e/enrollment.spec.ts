import { expect, test } from "@xenorepo/browser-testing";

test("[acceptance] enrollment reaches the sandbox checkout", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("$5.00 / month")).toBeVisible();
  await page.getByLabel("Email address").fill("reader@example.test");
  await page.getByText("CONTINUE TO PAYMENT").click();
  await expect(page.getByText("COMPLETE SANDBOX PAYMENT")).toBeVisible();
  await page.getByText("COMPLETE SANDBOX PAYMENT").click();
  await expect(page.locator("#message")).toHaveText("SUBSCRIPTION ACTIVE");
});

test("[visual] initial enrollment ledger", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("$5.00 / month")).toBeVisible();
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("enrollment-ledger.png", { maxDiffPixels: 2500 });
});
