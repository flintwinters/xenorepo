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

  await page.keyboard.press("Meta");
  await expect(page.getByLabel("shell-2 terminal")).toBeVisible();
  await page.keyboard.down("Meta");
  await page.keyboard.press("c");
  await page.keyboard.up("Meta");
  await expect(page.getByLabel("shell-3 terminal")).toHaveCount(0);
  const secondWindow = page.getByRole("region", { name: "shell-2" });
  const contextMenuAllowed = await page.getByLabel("shell-2 terminal").evaluate(element =>
    element.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, shiftKey: true })),
  );
  expect(contextMenuAllowed).toBe(false);
  await secondWindow.evaluate(element => { element.style.width = "540px"; element.style.height = "300px"; });
  const beforeMove = await secondWindow.boundingBox();
  const viewport = page.viewportSize();
  const gestureX = Math.min(beforeMove.x + 120, viewport.width - 20);
  const gestureY = Math.min(beforeMove.y + 100, viewport.height - 40);
  await page.keyboard.down("Shift");
  await page.mouse.move(gestureX, gestureY);
  await page.mouse.down();
  await page.mouse.move(gestureX + 28, gestureY + 22);
  await page.mouse.up();
  await page.keyboard.up("Shift");
  const afterMove = await secondWindow.boundingBox();
  expect(afterMove.x).toBeGreaterThan(beforeMove.x + 20);
  expect(afterMove.y).toBeGreaterThan(beforeMove.y + 15);
  expect(afterMove.width).toBe(beforeMove.width);
  expect(afterMove.height).toBe(beforeMove.height);

  await page.keyboard.down("Shift");
  await page.mouse.move(gestureX + 28, gestureY + 22);
  await page.mouse.down({ button: "right" });
  await page.mouse.move(gestureX + 64, gestureY + 48);
  await page.mouse.up({ button: "right" });
  await page.keyboard.up("Shift");
  const afterResize = await secondWindow.boundingBox();
  expect(afterResize.width).toBeGreaterThan(beforeMove.width + 25);
  expect(afterResize.height).toBeGreaterThan(beforeMove.height + 20);

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
