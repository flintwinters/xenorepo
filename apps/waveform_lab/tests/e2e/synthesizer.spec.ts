import { expect, test } from "@xenorepo/browser-testing";
import type { Page } from "@playwright/test";

async function connectAudio(page: Page, from: string, to: string): Promise<void> {
  await page.getByRole("button", { name: `${from} audio output` }).click();
  await page.getByRole("button", { name: `${to} audio input` }).click();
}

test("[acceptance] waveform, tempo, and two-bar polyphonic loop survive reload", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("SIGNAL READY")).toBeVisible();
  await expect(page.getByRole("gridcell")).toHaveCount(24 * 32);
  const loopLayout = await page.getByLabel("Scrollable two bar piano roll").evaluate((element) => ({
    clientHeight: element.clientHeight, scrollHeight: element.scrollHeight,
    overflowY: getComputedStyle(element).overflowY,
  }));
  expect(loopLayout.scrollHeight).toBeLessThanOrEqual(loopLayout.clientHeight + 1);
  expect(loopLayout.overflowY).toBe("hidden");
  expect(await page.evaluate(() => document.documentElement.scrollHeight > innerHeight)).toBe(true);

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
  await page.getByRole("button", { name: "Disconnect Gain 1 audio → Output 1" }).click();
  await expect(page.getByText("PATCH INCOMPLETE — SILENT")).toBeVisible();
  await page.getByRole("button", { name: "Gain 1 audio output" }).click();
  await page.getByRole("button", { name: "Output 1 audio input" }).click();
  await expect(page.getByText("SIGNAL READY")).toBeVisible();

  await page.getByRole("button", { name: "Add gain module" }).click();
  await expect(page.getByRole("region", { name: "Gain 2 module" })).toBeVisible();
  await page.getByRole("button", { name: "Remove Gain 2" }).click();
  await expect(page.getByRole("region", { name: "Gain 2 module" })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("SIGNAL READY")).toBeVisible();
});

test("[acceptance] the complete analog module palette exposes direct persistent controls", async ({ page }) => {
  await page.goto("/");
  for (const kind of ["noise", "adsr", "filter", "saturation", "delay", "chorus", "reverb",
    "compressor", "mixer", "lfo"])
    await page.getByRole("button", { name: `Add ${kind} module` }).click();

  for (const name of ["Noise", "Adsr", "Filter", "Saturation", "Delay", "Chorus", "Reverb",
    "Compressor", "Mixer", "Lfo"])
    await expect(page.getByRole("region", { name: `${name} 1 module` })).toBeAttached();
  await page.getByRole("button", { name: "Disconnect Waveform 1 audio → Gain 1" }).click();
  await page.getByRole("button", { name: "Disconnect Gain 1 audio → Output 1" }).click();
  const chain = ["Waveform 1", "Adsr 1", "Filter 1", "Saturation 1", "Delay 1", "Chorus 1",
    "Reverb 1", "Compressor 1", "Mixer 1", "Output 1"];
  for (let index = 0; index < chain.length - 1; index += 1)
    await connectAudio(page, chain[index] ?? "", chain[index + 1] ?? "");
  await connectAudio(page, "Noise 1", "Gain 1");
  await connectAudio(page, "Gain 1", "Mixer 1");
  await page.getByRole("button", { name: "Adsr 1 modulation output" }).click();
  await page.getByRole("button", { name: "Reverb 1 mix modulation input" }).click();
  await expect(page.getByText("SIGNAL READY")).toBeVisible();
  await page.getByRole("combobox", { name: "Filter 1 mode" }).selectOption("2");
  await page.getByRole("slider", { name: "Filter 1 frequency" }).fill("2400");
  await page.getByRole("slider", { name: "Saturation 1 drive" }).fill("6");
  await page.getByRole("slider", { name: "Delay 1 time" }).fill("0.5");
  await page.getByRole("slider", { name: "Reverb 1 mix" }).fill("0.4");
  await page.getByRole("slider", { name: "Lfo 1 rate" }).fill("4");
  await page.getByRole("button", { name: "Bypass Delay 1" }).click();
  await page.reload();

  await expect(page.getByRole("combobox", { name: "Filter 1 mode" })).toHaveValue("2");
  await expect(page.getByRole("slider", { name: "Filter 1 frequency" })).toHaveValue("2400");
  await expect(page.getByRole("slider", { name: "Saturation 1 drive" })).toHaveValue("6");
  await expect(page.getByRole("slider", { name: "Reverb 1 mix" })).toHaveValue("0.4");
  await expect(page.getByRole("button", { name: "Bypass Delay 1" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Reset Delay 1" }).click();
  await expect(page.getByRole("slider", { name: "Delay 1 time" })).toHaveValue("0.25");
  await expect(page.getByRole("button", { name: "Bypass Delay 1" })).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("slider", { name: "Filter 1 frequency" })).toHaveValue("2400");
  await page.getByRole("gridcell", { name: "C4, step 1", exact: true }).click();
  await page.getByRole("button", { name: "PLAY", exact: false }).click();
  await expect(page.getByText("RUNNING", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "STOP", exact: false }).click();
});

test("[acceptance] typed audio and modulation cables reject cycles atomically", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Add filter module" }).click();
  await page.getByRole("button", { name: "Add lfo module" }).click();
  await page.getByRole("button", { name: "Gain 1 audio output" }).click();
  await page.getByRole("button", { name: "Filter 1 audio input" }).click();
  await page.getByRole("button", { name: "Lfo 1 modulation output" }).click();
  await page.getByRole("button", { name: "Filter 1 frequency modulation input" }).click();
  await expect(page.getByRole("list", { name: "Connections" })).toContainText("Lfo 1 modulation → Filter 1 frequency");

  const before = await page.getByRole("list", { name: "Connections" }).getByRole("listitem").count();
  await page.getByRole("button", { name: "Filter 1 audio output" }).click();
  await page.getByRole("button", { name: "Gain 1 audio input" }).click();
  await expect(page.getByRole("alert")).toHaveText(/Connection rejected/);
  await expect(page.getByRole("list", { name: "Connections" }).getByRole("listitem")).toHaveCount(before);
  await page.reload();
  await expect(page.getByRole("list", { name: "Connections" })).toContainText("Lfo 1 modulation → Filter 1 frequency");
});

test("[acceptance] legacy patches migrate and malformed state recovers", async ({ page }) => {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("waveform-lab-fixture-seeded")) return;
    sessionStorage.setItem("waveform-lab-fixture-seeded", "true");
    const notes = Array.from({ length: 32 }, () => [] as number[]); notes[0]?.push(60);
    localStorage.setItem("waveform-lab-state-v1", JSON.stringify({ version: 1,
      modules: [{ id: "waveform-1", kind: "waveform", x: 28, y: 46 },
        { id: "gain-1", kind: "gain", x: 280, y: 112 },
        { id: "output-1", kind: "output", x: 520, y: 62 }],
      connections: [{ from: "waveform-1", to: "gain-1" }, { from: "gain-1", to: "output-1" }],
      samples: Array.from({ length: 128 }, (_, index) => Math.sin(index / 128 * Math.PI * 2)), notes, bpm: 133 }));
  });
  await page.goto("/");
  await expect(page.getByLabel("Tempo in BPM")).toHaveValue("133");
  await expect(page.getByRole("gridcell", { name: "C4, step 1", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("slider", { name: "Gain 1 gain" })).toHaveValue("0.8");
  await page.getByRole("slider", { name: "Gain 1 gain" }).fill("1.1");
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("waveform-lab-state-v1") ?? "null").version)).toBe(2);

  await page.evaluate(() => localStorage.setItem("waveform-lab-state-v1", "{malformed"));
  await page.reload();
  await expect(page.getByLabel("Tempo in BPM")).toHaveValue("120");
  await expect(page.getByText("SIGNAL READY")).toBeVisible();
});
