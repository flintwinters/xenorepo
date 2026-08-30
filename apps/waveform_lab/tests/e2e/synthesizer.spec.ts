import { expect, test } from "@xenorepo/browser-testing";

test("[acceptance] waveform, tempo, and two-bar polyphonic loop survive reload", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("SIGNAL READY")).toBeVisible();
  await expect(page.getByRole("gridcell")).toHaveCount(24 * 32);

  const first = page.getByRole("gridcell", { name: "C4, step 1", exact: true });
  const last = page.getByRole("gridcell", { name: "B5, step 32", exact: true });
  const chord = page.getByRole("gridcell", { name: "E4, step 1", exact: true });
  await first.click(); await chord.click(); await last.click();
  await page.getByLabel("Tempo in BPM").fill("146");
  await page.getByRole("button", { name: "square", exact: true }).click();
  await page.reload();

  await expect(page.getByLabel("Tempo in BPM")).toHaveValue("146");
  await expect(first).toHaveAttribute("aria-pressed", "true");
  await expect(chord).toHaveAttribute("aria-pressed", "true");
  await expect(last).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "PLAY", exact: false }).click();
  await expect(page.getByText("RUNNING", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "STOP", exact: false }).click();
  await expect(page.getByText("READY", { exact: true })).toBeVisible();
});

test("[acceptance] the waveform is drawable and undoable", async ({ page }) => {
  await page.goto("/");
  const editor = page.getByLabel("Draw one cycle waveform");
  await editor.scrollIntoViewIfNeeded();
  const before = await editor.locator("polyline").getAttribute("points");
  const bounds = await editor.boundingBox();
  if (!bounds) throw new Error("Waveform editor has no bounds");
  await page.mouse.move(bounds.x + 8, bounds.y + bounds.height * 0.75);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width - 8, bounds.y + bounds.height * 0.25, { steps: 12 });
  await page.mouse.up();
  const drawn = await editor.locator("polyline").getAttribute("points");
  expect(drawn).not.toBe(before);
  await page.getByRole("button", { name: "undo", exact: true }).click();
  await expect(editor.locator("polyline")).toHaveAttribute("points", before ?? "");
});

test("[acceptance] typed patch editing becomes silent and recovers", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Disconnect gain-1 from output-1" }).click();
  await expect(page.getByText("PATCH INCOMPLETE — SILENT")).toBeVisible();
  await page.getByRole("button", { name: "Connect output of gain-1" }).click();
  await page.getByRole("button", { name: "Connect input of output-1" }).click();
  await expect(page.getByText("SIGNAL READY")).toBeVisible();

  await page.getByRole("button", { name: "+ GAIN" }).click();
  await expect(page.locator(".module.gain")).toHaveCount(2);
  await page.getByRole("button", { name: "Remove gain module" }).last().click();
  await expect(page.locator(".module.gain")).toHaveCount(1);
  await page.reload();
  await expect(page.getByText("SIGNAL READY")).toBeVisible();
});
