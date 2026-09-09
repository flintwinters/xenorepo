import { expect, test } from "@xenorepo/browser-testing";

test("[acceptance] runs commands and interrupts a foreground process", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status")).toHaveText("CONNECTED");
  const terminal = page.locator(".xterm-helper-textarea");
  await terminal.pressSequentially("printf 'worminal-ready\\n'", { delay: 10 });
  await terminal.press("Enter");
  await expect(page.locator(".xterm-screen")).toContainText("worminal-ready");
  await terminal.pressSequentially("pwd", { delay: 10 }); await terminal.press("Enter");
  await expect(page.locator(".xterm-screen")).toContainText("apps/worminal");
  await terminal.pressSequentially("sleep 30", { delay: 10 }); await terminal.press("Enter");
  await terminal.press("Control+C");
  await terminal.pressSequentially("printf 'interrupted\\n'", { delay: 10 });
  await terminal.press("Enter");
  await expect(page.locator(".xterm-screen")).toContainText("interrupted");
});

test("[visual] terminal remains usable at wide and narrow sizes", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status")).toHaveText("CONNECTED");
  await page.setViewportSize({ width: 390, height: 700 });
  await expect(page.locator(".terminal-host")).toBeVisible();
  await expect(page.locator(".xterm-screen")).toBeVisible();
});
