import { expect, test } from "@xenorepo/browser-testing";

test("[acceptance] the GUI loop survives reload and controls playback", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("SIGNAL READY")).toBeVisible();
  await expect(page.getByRole("gridcell")).toHaveCount(24 * 32);
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

  const first = page.getByRole("gridcell", { name: "C4, step 1", exact: true });
  const last = page.getByRole("gridcell", { name: "B5, step 32", exact: true });
  await first.click(); await last.click();
  await page.getByLabel("Tempo in BPM").fill("146");
  await page.getByLabel("Tempo in BPM").press("Tab");
  await page.reload();

  await expect(page.getByLabel("Tempo in BPM")).toHaveValue("146");
  await expect(first).toHaveAttribute("aria-pressed", "true");
  await expect(last).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "PLAY", exact: false }).click();
  await expect(page.getByText("RUNNING", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "STOP", exact: false }).click();
  await expect(page.getByText("READY", { exact: true })).toBeVisible();
});

test("[acceptance] raw YAML is the only synth setup surface", async ({ page }) => {
  await page.goto("/");
  const editor = page.getByLabel("Synth setup YAML editor");
  await expect(editor).toContainText("modules:");
  await expect(editor).toContainText("samples:");
  await expect(editor).not.toContainText("notes:");
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
  await page.keyboard.type("synth:\n  modules: invalid");
  await page.getByRole("button", { name: "APPLY YAML" }).click();
  await expect(page.getByRole("alert")).toContainText("violates");
  await expect(page.getByText("SIGNAL READY")).toBeVisible();

  await page.getByRole("button", { name: "REVERT DRAFT" }).click();
  await editor.locator(".cm-content").click();
  await page.keyboard.press("Control+f");
  await editor.getByRole("textbox", { name: "Find" }).fill("gain: 0.8");
  await editor.getByRole("textbox", { name: "Replace" }).fill("gain: 1.25");
  await editor.getByRole("button", { name: "replace all", exact: true }).click();
  await page.getByRole("button", { name: "APPLY YAML" }).click();
  await expect(page.getByText("Synth YAML applied and saved.")).toBeVisible();
  await page.reload();
  await expect(editor).toContainText("gain: 1.25");
  await expect(page.getByRole("gridcell", { name: "C4, step 1", exact: true }))
    .toHaveAttribute("aria-pressed", "true");
});

test("[acceptance] legacy state migrates to nested YAML and malformed storage recovers", async ({ page }) => {
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
  await page.getByLabel("Tempo in BPM").fill("134");
  await page.getByLabel("Tempo in BPM").press("Tab");
  expect(await page.evaluate(() => localStorage.getItem("waveform-lab-state-v1")))
    .toContain("version: 2\nsynth:");

  await page.evaluate(() => localStorage.setItem("waveform-lab-state-v1", "{malformed"));
  await page.reload();
  await expect(page.getByLabel("Tempo in BPM")).toHaveValue("120");
  await expect(page.getByText("SIGNAL READY")).toBeVisible();
});
