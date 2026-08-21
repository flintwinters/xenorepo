const { expect, test } = require("@playwright/test");

async function openCleanDesktop(page) {
  const response = await page.request.get("/api/workspace");
  const state = await response.json();
  await Promise.all(state.windows.map(window => page.request.delete(
    `/api/workspace/windows/${window.id}`,
  )));
  await page.request.put("/api/workspace", { data: { windows: [], shortcuts: [{
    action: "new-shell", key: "Meta", control: false, alt: false, shift: false, meta: false,
  }] } });
  await page.goto("/worminal");
}

test("uses a transparent pink tilde favicon", async ({ page }) => {
  await page.goto("/worminal");
  const href = await page.locator('link[rel="icon"]').getAttribute("href");
  const svg = decodeURIComponent(href.split(",")[1]);

  expect(svg).toContain('stroke="#ff69b4"');
  expect(svg).toContain('fill="none"');
  expect(svg).not.toContain("<rect");
});

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
  await openCleanDesktop(page);

  await expect(page.getByText("WORMINAL", { exact: true })).toBeVisible();
  await expect(page.getByText("1 SHELL CONNECTED", { exact: true })).toBeVisible();
  await expect(page.getByLabel("shell-1 terminal")).toBeVisible();
  const metrics = await page.getByLabel("shell-1 terminal").locator(".xterm-rows > div").evaluateAll(rows => ({
    fontSize: getComputedStyle(rows[0].parentElement).fontSize,
    rowHeight: rows[0].getBoundingClientRect().height,
  }));
  expect(metrics.fontSize).toBe("11px");
  expect(metrics.rowHeight).toBe(9);

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
  const hostContextMenuAllowed = await page.locator("worminal-desktop").evaluate(element =>
    element.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, shiftKey: true })),
  );
  expect(hostContextMenuAllowed).toBe(false);
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
  await openCleanDesktop(page);
  await expect(page.getByText("1 SHELL CONNECTED", { exact: true })).toBeVisible();

  const terminal = page.getByLabel("shell-1 terminal");
  await terminal.locator(".xterm-helper-textarea").pressSequentially(
    "printf 'worminal-live-check\\n'",
  );
  await terminal.locator(".xterm-helper-textarea").press("Enter");

  await expect(terminal.locator(".xterm-screen")).toContainText("worminal-live-check");
});

test("restores a server-saved desktop after reload", async ({ page }) => {
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
  await openCleanDesktop(page);
  await expect(page.getByLabel("shell-1 terminal")).toBeVisible();
  await page.getByText("+ NEW SHELL", { exact: true }).click();
  await expect(page.getByLabel("shell-2 terminal")).toBeVisible();
  const second = page.getByRole("region", { name: "shell-2" });
  const before = await second.boundingBox();
  await page.keyboard.down("Shift");
  await page.mouse.move(before.x + 100, before.y + 10);
  await page.mouse.down();
  await page.mouse.move(before.x + 145, before.y + 42);
  await page.mouse.up();
  await page.keyboard.up("Shift");
  const moved = await second.boundingBox();
  await expect.poll(async () => page.evaluate(async () => {
    const state = await fetch("/api/workspace").then(response => response.json());
    return state.windows.find(window => window.title === "shell-2")?.x;
  })).toBe(Math.round(moved.x));

  await page.reload();
  await expect(page.getByLabel("shell-1 terminal")).toBeVisible();
  await expect(page.getByLabel("shell-2 terminal")).toBeVisible();
  expect((await page.getByRole("region", { name: "shell-2" }).boundingBox()).x).toBe(Math.round(moved.x));
});

test("customizes and restores the new-shell hotkey from settings", async ({ page }) => {
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
  await openCleanDesktop(page);
  await expect(page.getByLabel("shell-1 terminal")).toBeVisible();
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("dialog", { name: "SETTINGS" })).toBeVisible();
  const shortcut = page.getByLabel("New shell shortcut");
  await shortcut.focus();
  await page.keyboard.down("Control");
  await page.keyboard.down("Alt");
  await page.keyboard.press("n");
  await page.keyboard.up("Alt");
  await page.keyboard.up("Control");
  await expect(shortcut).toHaveValue("Ctrl + Alt + n");
  await page.getByRole("button", { name: "SAVE" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(async () => page.evaluate(async () => {
    const state = await fetch("/api/workspace").then(response => response.json());
    return state.shortcuts[0];
  })).toEqual({ action: "new-shell", key: "n", control: true, alt: true, shift: false, meta: false });

  await page.keyboard.down("Control");
  await page.keyboard.down("Alt");
  await page.keyboard.press("n");
  await page.keyboard.up("Alt");
  await page.keyboard.up("Control");
  await expect(page.getByLabel("shell-2 terminal")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByLabel("New shell shortcut")).toHaveValue("Ctrl + Alt + n");
});

test("changes the access password from settings", async ({ page }) => {
  let submitted;
  await page.route("**/api/access/password", async route => {
    submitted = route.request().postDataJSON();
    await route.fulfill({ status: 204 });
  });
  await openCleanDesktop(page);
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByLabel("Current access password").fill("current-secret");
  await page.getByLabel("New access password", { exact: true }).fill("replacement-secret");
  await page.getByLabel("Confirm new access password", { exact: true }).fill("replacement-secret");
  await page.getByRole("button", { name: "SAVE" }).click();

  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(submitted).toEqual({
    current_password: "current-secret", new_password: "replacement-secret",
  });
});

test("uses browser dialogs to grant remote access", async ({ page }) => {
  let authorized = false;
  const submitted = [];
  await page.route("**/api/workspace", async route => {
    if (!authorized) {
      await route.fulfill({ status: 401, body: "Worminal requires its access password." });
      return;
    }
    await route.fulfill({ json: { windows: [], shortcuts: [{
      action: "new-shell", key: "Meta", control: false, alt: false, shift: false, meta: false,
    }] } });
  });
  await page.route("**/api/access", async route => {
    const password = route.request().postDataJSON().password;
    submitted.push(password);
    authorized = password === "correct-secret";
    await route.fulfill({ status: authorized ? 204 : 401 });
  });

  const dialogs = [];
  let prompts = 0;
  page.on("dialog", async dialog => {
    dialogs.push({ type: dialog.type(), message: dialog.message() });
    if (dialog.type() === "prompt") {
      await dialog.accept(prompts++ ? "correct-secret" : "wrong-secret");
    } else {
      await dialog.accept();
    }
  });

  await page.goto("/worminal");
  await expect.poll(() => submitted).toEqual(["wrong-secret", "correct-secret"]);
  expect(dialogs).toEqual([
    { type: "prompt", message: "Worminal access password:" },
    { type: "alert", message: "The password was not accepted." },
    { type: "prompt", message: "Worminal access password:" },
  ]);
});

test("mirrors windows and live terminal output across views", async ({ page, context }) => {
  await openCleanDesktop(page);
  await expect(page.getByText("1 SHELL CONNECTED", { exact: true })).toBeVisible();
  const second = await context.newPage();
  await second.goto("/worminal");
  await expect(second.getByLabel("shell-1 terminal")).toBeVisible();

  const firstTerminal = page.getByLabel("shell-1 terminal");
  await firstTerminal.locator(".xterm-helper-textarea").pressSequentially(
    "printf 'worminal-mirrored-output\\n'",
  );
  await firstTerminal.locator(".xterm-helper-textarea").press("Enter");
  await expect(firstTerminal.locator(".xterm-screen")).toContainText("worminal-mirrored-output");
  await expect(second.getByLabel("shell-1 terminal").locator(".xterm-screen"))
    .toContainText("worminal-mirrored-output");

  await page.getByText("+ NEW SHELL", { exact: true }).click();
  await expect(second.getByLabel("shell-2 terminal")).toBeVisible({ timeout: 3000 });

  await Promise.all([
    page.getByText("+ NEW SHELL", { exact: true }).click(),
    second.getByText("+ NEW SHELL", { exact: true }).click(),
  ]);
  await expect.poll(async () => page.evaluate(async () =>
    (await fetch("/api/workspace").then(response => response.json())).windows.length,
  )).toBe(4);
});
