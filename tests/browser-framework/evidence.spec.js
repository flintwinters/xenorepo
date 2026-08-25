const {
  expect, installInputEvidence, keyboardSequence, mousePath, readInputEvidence, test,
  touchPath, validateInputEvidence,
} = require("@xenorepo/browser-testing");

test.beforeEach(async ({ page }) => {
  await installInputEvidence(page);
  await page.goto("data:text/html,<style>*{touch-action:none}</style>"
    + "<button id='target'>target</button><input id='input'>");
});

test("[browser-integration] accepts trusted mouse paths and rejects synthetic equivalents", async ({ page }) => {
  await mousePath(page, [{ x: 2, y: 2 }, { x: 20, y: 20 }, { x: 40, y: 25 }]);
  expect(validateInputEvidence(await readInputEvidence(page), "mouse").accepted).toBe(true);
  await page.evaluate(() => document.dispatchEvent(new PointerEvent("pointerdown", {
    pointerType: "mouse", pointerId: 9, bubbles: true,
  })));
  const synthetic = (await readInputEvidence(page)).filter(record => record.pointerId === 9);
  expect(validateInputEvidence(synthetic, "mouse")).toMatchObject({
    accepted: false, reason: "EVIDENCE_UNTRUSTED",
  });
});

test("[acceptance] accepts trusted native touch paths", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "narrow-viewport-chromium", "one native touch canary");
  await touchPath(page, [{ x: 2, y: 2 }, { x: 20, y: 20 }, { x: 40, y: 25 }]);
  const records = await readInputEvidence(page);
  expect(validateInputEvidence(records, "touch"), JSON.stringify(records)).toMatchObject({ accepted: true });
});

test("[acceptance] accepts balanced trusted keyboard sequences", async ({ page }) => {
  await page.locator("#input").focus();
  await keyboardSequence(page, ["A", "Enter"]);
  expect(validateInputEvidence(await readInputEvidence(page), "keyboard").accepted).toBe(true);
});

test("[browser-integration] rejects wrong modalities incomplete paths and cancellation", async () => {
  const base = { schemaVersion: 1, trusted: true, timestamp: 1, pointerId: 1,
    pointerType: "mouse", key: null, canceled: false, target: "button" };
  const incomplete = [{ ...base, type: "pointerdown" }, { ...base, type: "pointerup" }];
  expect(validateInputEvidence(incomplete, "mouse").reason).toBe("EVIDENCE_POINTER_INCOMPLETE");
  expect(validateInputEvidence(incomplete, "touch").reason).toBe("EVIDENCE_POINTER_INCOMPLETE");
  const canceled = [...incomplete, { ...base, type: "pointercancel", canceled: true }];
  expect(validateInputEvidence(canceled, "mouse").reason).toBe("EVIDENCE_POINTER_CANCELED");
});
