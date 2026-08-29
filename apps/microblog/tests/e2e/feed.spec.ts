import { expect, test } from "@xenorepo/browser-testing";

test("[acceptance] a visitor can select account registration", async ({ page }) => {
  await page.goto("/");
  const account = page.getByRole("button", { name: "ACCOUNT", exact: true });
  if (await account.isVisible()) await account.click();
  await page.locator("#registerTab").click();
  await expect(page.locator("#authSubmit")).toHaveText("REGISTER");
  await expect(page.locator("#authMessage")).toHaveText("CHOOSE NEW ACCOUNT CREDENTIALS");
});

test("[visual] empty public wire", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("NO TRANSMISSIONS RECORDED")).toBeVisible();
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("public-wire.png", {
    mask: [page.locator("#lastSync")],
    maxDiffPixels: 300,
  });
});
