const { expect, test } = require("@playwright/test");

test("creates and manages independent terminal windows", async ({ page }) => {
  await page.addInitScript(() => {
    globalThis.WebSocket = class SocketDouble {
      static OPEN = 1;
      readyState = 0;
      set onopen(handler) { this.readyState = 1; setTimeout(() => handler({}), 0); }
      get onopen() { return undefined; }
      send() {}
      close() { this.readyState = 3; this.onclose?.({}); }
    };
  });
  await page.goto("/");

  await expect(page.getByText("WORMINAL", { exact: true })).toBeVisible();
  await expect(page.getByText("1 SHELL CONNECTED", { exact: true })).toBeVisible();
  await expect(page.getByLabel("shell-1 terminal")).toBeVisible();

  await page.getByRole("button", { name: "+ NEW SHELL" }).click();
  await expect(page.getByLabel("shell-2 terminal")).toBeVisible();
  await page.getByRole("button", { name: "Minimize shell-2" }).click();
  await expect(page.getByLabel("shell-2 terminal")).toBeHidden();
  await page.getByRole("button", { name: "shell-2" }).click();
  await expect(page.getByLabel("shell-2 terminal")).toBeVisible();
  await page.getByRole("button", { name: "Maximize shell-2" }).click();
  await expect(page.getByRole("region", { name: "shell-2" })).toHaveClass(/maximized/);
  await page.getByRole("button", { name: "Close shell-2" }).click();
  await expect(page.getByLabel("shell-2 terminal")).toHaveCount(0);
});

test("executes a command in a real localhost shell", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("1 SHELL CONNECTED", { exact: true })).toBeVisible();

  const terminal = page.getByLabel("shell-1 terminal");
  await terminal.locator(".xterm-helper-textarea").pressSequentially(
    "printf 'worminal-live-check\\n'",
  );
  await terminal.locator(".xterm-helper-textarea").press("Enter");

  await expect(terminal.locator(".xterm-screen")).toContainText("worminal-live-check");
});
