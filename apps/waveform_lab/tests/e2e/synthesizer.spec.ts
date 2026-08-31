import { expect, test } from "@xenorepo/browser-testing";
import type { Locator, Page } from "@playwright/test";

async function replaceYaml(page: Page, editor: Locator, find: string, replacement: string): Promise<void> {
  await editor.locator(".cm-content").click();
  await page.keyboard.press("Control+f");
  await editor.getByRole("textbox", { name: "Find" }).fill(find);
  await editor.getByRole("textbox", { name: "Replace" }).fill(replacement);
  await editor.getByRole("button", { name: "replace all", exact: true }).click();
  await page.keyboard.press("Escape");
}

async function dragBetween(page: Page, from: Locator, to: Locator): Promise<void> {
  const start = await from.boundingBox(); const end = await to.boundingBox();
  if (!start || !end) throw new Error("Loop cells must have visible bounds");
  await page.mouse.move(start.x + start.width / 2, start.y + start.height / 2);
  await page.mouse.down();
  await page.mouse.move(end.x + end.width / 2, end.y + end.height / 2, { steps: 4 });
  await page.mouse.up();
}

test("[acceptance] the GUI loop survives reload and controls playback", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("Loop instrument")).toBeVisible();
  await expect(page.getByRole("gridcell")).toHaveCount(48 * 32);
  await expect(page.getByLabel("Patch bay")).toHaveCount(0);
  await expect(page.getByLabel("Draw one cycle waveform")).toHaveCount(0);
  const overflow = await page.evaluate(() => ({
    documentX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    documentY: document.documentElement.scrollHeight > document.documentElement.clientHeight,
    pianoX: document.querySelector<HTMLElement>(".piano-scroll")!.scrollWidth
      > document.querySelector<HTMLElement>(".piano-scroll")!.clientWidth,
    pianoY: document.querySelector<HTMLElement>(".piano-scroll")!.scrollHeight
      > document.querySelector<HTMLElement>(".piano-scroll")!.clientHeight,
  }));
  expect(overflow).toEqual({ documentX: false, documentY: false, pianoX: false, pianoY: false });
  await expect(page.getByRole("gridcell", { name: "C3, step 1", exact: true })).toBeVisible();
  await expect(page.getByRole("gridcell", { name: "B6, step 32", exact: true })).toBeVisible();
  const natural = await page.getByRole("gridcell", { name: "C4, step 2", exact: true })
    .evaluate((cell) => getComputedStyle(cell).backgroundColor);
  const sharp = await page.getByRole("gridcell", { name: "C♯4, step 2", exact: true })
    .evaluate((cell) => getComputedStyle(cell).backgroundColor);
  expect(natural).toBe("rgb(37, 40, 39)");
  expect(sharp).toBe("rgb(29, 32, 33)");

  const first = page.getByRole("gridcell", { name: "C4, step 1", exact: true });
  const last = page.getByRole("gridcell", { name: "B5, step 32", exact: true });
  await first.click(); await last.click();
  await page.getByLabel("Tempo in BPM").fill("146");
  await page.getByLabel("Tempo in BPM").press("Tab");
  await page.getByLabel("App volume").fill("0.35");
  await page.reload();

  await expect(page.getByLabel("Tempo in BPM")).toHaveValue("146");
  await expect(page.getByLabel("App volume")).toHaveValue("0.35");
  await expect(page.getByText("35%", { exact: true })).toBeVisible();
  await expect(first).toHaveAttribute("aria-pressed", "true");
  await expect(last).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "PLAY", exact: false }).click();
  await expect(page.getByText("RUNNING", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "STOP", exact: false }).click();
  await expect(page.getByText("READY", { exact: true })).toBeVisible();
});

test("[acceptance] the piano roll reaches arbitrary positive and negative octaves", async ({ page }) => {
  await page.goto("/");
  const octave = page.getByLabel("Highest visible octave");
  await octave.fill("20");
  await octave.press("Tab");
  const high = page.getByRole("gridcell", { name: "C20, step 1", exact: true });
  await high.click();

  await octave.fill("-5");
  await octave.press("Tab");
  const low = page.getByRole("gridcell", { name: "C-5, step 2", exact: true });
  await low.click();

  await page.reload();
  await octave.fill("20");
  await octave.press("Tab");
  await expect(high).toHaveAttribute("aria-pressed", "true");
  await octave.fill("-5");
  await octave.press("Tab");
  await expect(low).toHaveAttribute("aria-pressed", "true");
});

test("[acceptance] raw YAML is the only synth setup surface", async ({ page }) => {
  await page.goto("/");
  const editor = page.getByLabel("Synth setup YAML editor");
  await expect(editor).toContainText("kick:");
  const options = page.getByLabel("Loop instrument").locator("option");
  await expect(options).toHaveText(["kick", "snare", "stick", "bass", "lead"]);
  await expect(editor).not.toContainText("synth:");
  await expect(editor).not.toContainText("instruments:");
  await expect(editor).not.toContainText("name: main");
  await expect(editor).toContainText("modules:");
  await expect(editor).not.toContainText("samples:");
  await expect(editor).not.toContainText("parameters:");
  await expect(editor).toContainText("from: kick-oscillator");
  await expect(editor).toContainText("to: kick-filter");
  await expect(editor).not.toContainText("kind: output");
  await expect(editor).not.toContainText("type: audio");
  await expect(editor).not.toContainText("notes:");
  await expect(editor).not.toContainText("volume:");
  await expect(editor).not.toContainText(/\b[xy]:/);
  await editor.locator(".cm-content").click();
  await page.keyboard.press("Control+End");
  await expect(editor).toContainText("from: bass-gain");
  await expect(editor).toContainText("lead:");
  await expect(editor).toContainText("to: output");
  const theme = await editor.evaluate((element) => ({
    editor: getComputedStyle(element.querySelector(".cm-editor")!).backgroundColor,
    gutter: getComputedStyle(element.querySelector(".cm-gutters")!).backgroundColor,
    tokens: [...element.querySelectorAll<HTMLElement>(".cm-content span")]
      .map((token) => getComputedStyle(token).color),
  }));
  expect(theme.editor).toBe("rgb(40, 40, 40)");
  expect(theme.gutter).toBe("rgb(29, 32, 33)");
  expect(new Set(theme.tokens).size).toBeGreaterThan(1);
  await page.getByRole("gridcell", { name: "C4, step 1", exact: true }).click();

  await editor.locator(".cm-content").click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type("main:\n  modules: invalid");
  await page.getByRole("button", { name: "APPLY YAML" }).click();
  await expect(page.getByRole("alert")).toContainText("violates");
  await expect(page.getByLabel("Loop instrument").locator("option")).toHaveCount(5);

  await page.getByRole("button", { name: "REVERT DRAFT" }).click();
  await replaceYaml(page, editor, "#b8bb26", "#d3869b");
  await page.getByRole("button", { name: "APPLY YAML" }).click();
  await expect(page.getByText("Synth YAML applied and saved.")).toBeVisible();
  await page.reload();
  await editor.locator(".cm-content").click();
  await page.keyboard.press("Control+End");
  await expect(editor).toContainText('color: "#d3869b"');
  await expect(page.getByRole("gridcell", { name: "C4, step 1", exact: true }))
    .toHaveAttribute("aria-pressed", "true");
});

test("[acceptance] YAML typing suggests module kinds and their parameters", async ({ page }) => {
  await page.goto("/");
  const content = page.getByLabel("Synth setup YAML editor").locator(".cm-content");
  await content.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("\n    - id: probe-filter\n      kind: fi");
  const completions = page.locator(".cm-tooltip-autocomplete");
  await expect(completions).toBeVisible();
  await expect(completions).toContainText("filter");
  await completions.getByText("filter", { exact: true }).click();
  await page.keyboard.type("\n      freq");
  await page.keyboard.press("Control+Space");
  await expect(completions).toBeVisible();
  await expect(completions).toContainText("frequency");
});

test("[acceptance] named instruments color independent loop notes", async ({ page }) => {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("multi-instrument-seeded")) return;
    sessionStorage.setItem("multi-instrument-seeded", "true");
    localStorage.setItem("waveform-lab-state-v1", JSON.stringify({ version: 9,
    synth: { instruments: [
      { name: "bass", color: "#fb4934", waveform: "square", modules: [
        { id: "bass-wave", kind: "waveform", detune: -120,
          connections: [{ from: "bass-wave", to: "bass-output" }] },
        { id: "bass-output", kind: "output", level: 0.7 }] },
      { name: "main", color: "#b8bb26", modules: [
        { id: "main-wave", kind: "waveform",
          connections: [{ from: "main-wave", to: "main-output" }] },
        { id: "main-output", kind: "output" }] },
      ] }, loop: { bpm: 120, volume: 0.8, notes: Array.from({ length: 32 }, () => []) },
    }));
  });
  await page.goto("/");
  const editor = page.getByLabel("Synth setup YAML editor");
  await expect(editor).toContainText("bass:");
  await expect(editor).toContainText("main:");
  await expect(editor).toContainText("output:");
  await expect(editor).toContainText("level: 0.7");
  await expect(editor).toContainText("to: output");
  await expect(editor).not.toContainText("bass-output");
  await expect(editor).not.toContainText("main-output");
  await expect(editor).not.toContainText("name: bass");
  const selector = page.getByLabel("Loop instrument");
  await expect(selector.locator("option")).toHaveCount(2);
  await selector.selectOption("bass");
  const bassNote = page.getByRole("gridcell", { name: "C3, step 3", exact: true });
  await bassNote.click();
  await expect(bassNote).toHaveCSS("background-color", "rgb(251, 73, 52)");
  await selector.selectOption("main");
  const leadNote = page.getByRole("gridcell", { name: "C4, step 3", exact: true });
  await leadNote.click();
  await expect(leadNote).toHaveCSS("background-color", "rgb(184, 187, 38)");
  await page.reload();
  await expect(selector.locator("option")).toHaveCount(2);
  await expect(bassNote).toHaveCSS("background-color", "rgb(251, 73, 52)");
  await expect(leadNote).toHaveCSS("background-color", "rgb(184, 187, 38)");
  await page.getByRole("button", { name: "PLAY", exact: false }).click();
  await expect(page.getByText("RUNNING", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "STOP", exact: false }).click();
});

test("[acceptance] the prior default setup gains the five-voice starter kit", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("waveform-lab-state-v1", `version: 12
main:
  color: "#b8bb26"
  modules:
    - id: waveform-1
      kind: waveform
      connections:
        - from: waveform-1
          to: gain-1
    - id: gain-1
      kind: gain
      connections:
        - from: gain-1
          to: output
bass:
  color: "#fb4934"
  waveform: square
  modules:
    - id: bass-waveform-1
      kind: waveform
      connections:
        - from: bass-waveform-1
          to: bass-gain-1
    - id: bass-gain-1
      kind: gain
      connections:
        - from: bass-gain-1
          to: output
loop:
  bpm: 120
  volume: 0.8
  notes:
    - - pitch: 60
        instrument: main
${Array.from({ length: 31 }, () => "    - []").join("\n")}
`));
  await page.goto("/");
  await expect(page.getByLabel("Loop instrument").locator("option"))
    .toHaveText(["kick", "snare", "stick", "bass", "lead"]);
  await expect(page.getByRole("gridcell", { name: "C4, step 1", exact: true }))
    .toHaveCSS("background-color", "rgb(184, 187, 38)");
});

test("[acceptance] box selection supports keyboard clipboard and group dragging", async ({ page }) => {
  await page.goto("/");
  const c4s1 = page.getByRole("gridcell", { name: "C4, step 1", exact: true });
  const d4s2 = page.getByRole("gridcell", { name: "D4, step 2", exact: true });
  await c4s1.click(); await d4s2.click();
  await dragBetween(page, c4s1, d4s2);
  await expect(page.locator(".note-cell.selected")).toHaveCount(6);
  await expect(c4s1).toHaveClass(/selection-left/);
  await expect(c4s1).toHaveClass(/selection-bottom/);
  await expect(d4s2).toHaveClass(/selection-top/);
  await expect(d4s2).toHaveClass(/selection-right/);
  await expect(page.getByText("6 SELECTED", { exact: true })).toBeVisible();

  await page.keyboard.press("Control+x");
  await expect(c4s1).toHaveAttribute("aria-pressed", "false");
  await expect(d4s2).toHaveAttribute("aria-pressed", "false");
  await page.keyboard.press("Control+v");
  await expect(c4s1).toHaveAttribute("aria-pressed", "true");
  await expect(d4s2).toHaveAttribute("aria-pressed", "true");

  const c5s5 = page.getByRole("gridcell", { name: "C5, step 5", exact: true });
  await dragBetween(page, c4s1, c5s5);
  await expect(c4s1).toHaveAttribute("aria-pressed", "false");
  await expect(d4s2).toHaveAttribute("aria-pressed", "false");
  await expect(c5s5).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("gridcell", { name: "D5, step 6", exact: true }))
    .toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(c5s5).toHaveAttribute("aria-pressed", "true");
});

test("[acceptance] coordinate-bearing state migrates and malformed storage recovers", async ({ page }) => {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("waveform-lab-fixture-seeded")) return;
    sessionStorage.setItem("waveform-lab-fixture-seeded", "true");
    const notes = Array.from({ length: 32 }, () => [] as number[]); notes[0]?.push(60);
    localStorage.setItem("waveform-lab-state-v1", JSON.stringify({ version: 2,
      modules: [{ id: "waveform-1", kind: "waveform", x: 28, y: 46, parameters: { detune: 0 } },
        { id: "gain-1", kind: "gain", x: 280, y: 112, parameters: { gain: 0.8 } },
        { id: "output-1", kind: "output", x: 520, y: 62, parameters: { level: 0.8 } }],
      connections: [{ from: "waveform-1", to: "gain-1", type: "audio" },
        { from: "gain-1", to: "output-1", type: "audio" }],
      samples: Array.from({ length: 128 }, (_, index) => Math.sin(index / 128 * Math.PI * 2)), notes, bpm: 133 }));
  });
  await page.goto("/");
  await expect(page.getByLabel("Tempo in BPM")).toHaveValue("133");
  await page.getByLabel("Tempo in BPM").fill("134");
  await page.getByLabel("Tempo in BPM").press("Tab");
  expect(await page.evaluate(() => localStorage.getItem("waveform-lab-state-v1")))
    .toContain("version: 13\nmain:");
  expect(await page.evaluate(() => localStorage.getItem("waveform-lab-state-v1"))).not.toContain("synth:");
  expect(await page.evaluate(() => localStorage.getItem("waveform-lab-state-v1"))).not.toContain("instruments:");
  expect(await page.evaluate(() => localStorage.getItem("waveform-lab-state-v1"))).not.toMatch(/\b[xy]:/);
  expect(await page.evaluate(() => localStorage.getItem("waveform-lab-state-v1"))).not.toContain("samples:");
  expect(await page.evaluate(() => localStorage.getItem("waveform-lab-state-v1"))).not.toContain("parameters:");
  expect(await page.evaluate(() => localStorage.getItem("waveform-lab-state-v1"))).not.toContain("name: main");
  expect(await page.evaluate(() => localStorage.getItem("waveform-lab-state-v1"))).not.toContain("kind: output");
  expect(await page.evaluate(() => localStorage.getItem("waveform-lab-state-v1"))).toContain("to: output");
  await expect(page.getByLabel("Synth setup YAML editor")).not.toContainText("waveform:");
  expect(await page.evaluate(() => localStorage.getItem("waveform-lab-state-v1"))).not.toContain("type: audio");
  await expect(page.getByLabel("App volume")).toHaveValue("0.8");

  await page.evaluate(() => localStorage.setItem("waveform-lab-state-v1", "{malformed"));
  await page.reload();
  await expect(page.getByLabel("Tempo in BPM")).toHaveValue("120");
  await expect(page.getByLabel("Loop instrument").locator("option")).toHaveCount(5);
});
