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
