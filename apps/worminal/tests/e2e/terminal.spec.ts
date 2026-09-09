import { expect, test } from "@xenorepo/browser-testing";

test("[acceptance] runs commands and interrupts a foreground process", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status")).toHaveText("CONNECTED");
  const terminal = page.locator(".xterm-helper-textarea");
  await terminal.pressSequentially("printf 'worminal-ready\\n'", { delay: 10 });
  await terminal.press("Enter");
  await expect(page.locator(".xterm-screen")).toContainText("worminal-ready");
  await terminal.pressSequentially("printf '__PWD__%s\\n' \"$PWD\"", { delay: 10 });
  await terminal.press("Enter");
  await expect(page.locator(".xterm-screen")).toContainText("__PWD__/");
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

test("[acceptance] moves and resizes the terminal window", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status")).toHaveText("CONNECTED");
  const frame = page.locator(".terminal-window"), before = await frame.boundingBox();
  const titleBox = await page.getByRole("button", { name: "Move terminal window" }).boundingBox();
  if (!before || !titleBox) throw new Error("Terminal window has no measurable bounds");
  await page.mouse.move(titleBox.x + 40, titleBox.y + titleBox.height / 2);
  await page.mouse.down(); await page.mouse.move(titleBox.x + 100, titleBox.y + 50); await page.mouse.up();
  const moved = await frame.boundingBox();
  expect(moved?.x).toBeGreaterThan(before.x + 20);
  const handleBox = await page.getByRole("separator", { name: "Resize terminal window" }).boundingBox();
  if (!moved || !handleBox) throw new Error("Resize handle has no measurable bounds");
  await page.mouse.move(handleBox.x + 14, handleBox.y + 14);
  await page.mouse.down(); await page.mouse.move(handleBox.x - 66, handleBox.y - 46); await page.mouse.up();
  const resized = await frame.boundingBox();
  if (moved.width > 400) expect(resized?.width).toBeLessThan(moved.width - 50);
  else expect(resized?.width).toBeGreaterThanOrEqual(320);
  expect(resized?.height).toBeLessThan(moved.height - 30);
});
