const { expect, test } = require("@xenorepo/browser-testing");

test("[acceptance] transmits and restores a durable public message", async ({ page }) => {
  await page.goto("/");
  const send = page.getByRole("button", { name: /SEND/ });
  await expect(send).toBeEnabled();
  await page.getByLabel("Display name").fill("Grace");
  const body = `Browser proof ${Date.now()}`;
  await page.getByLabel("Message").fill(body);
  await send.click();
  await expect(page.getByText(body)).toBeVisible();
  await expect(page.getByLabel("Message")).toHaveValue("");
  await page.reload();
  await expect(page.getByText(body)).toBeVisible();
});

test("[visual] initial common room", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: /SEND/ })).toBeEnabled();
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("common-room.png", {
    mask: [
      page.locator(".stream"),
      page.locator(".details dd:nth-of-type(3)"),
      page.locator(".status span:last-child"),
    ],
    maxDiffPixels: 5500,
  });
});
