"use strict";

const { expect, test: base } = require("@playwright/test");

const EVIDENCE_SCHEMA_VERSION = 1;
const acknowledgedHttpStatuses = new WeakMap();

function acknowledgeHttpFailures(page, statuses) {
  acknowledgedHttpStatuses.set(page, new Set(statuses));
}

async function installInputEvidence(page) {
  await page.addInitScript(({ schemaVersion }) => {
    const records = [];
    const types = ["pointerdown", "pointermove", "pointerup", "pointercancel",
      "touchstart", "touchmove", "touchend", "touchcancel", "mousedown", "mousemove",
      "mouseup", "click", "keydown", "keyup"];
    for (const type of types) document.addEventListener(type, event => {
      records.push({
        schemaVersion,
        type: event.type,
        trusted: event.isTrusted,
        timestamp: performance.timeOrigin + event.timeStamp,
        pointerId: event.pointerId ?? null,
        pointerType: event.pointerType ?? null,
        key: event.key ?? null,
        canceled: event.type.endsWith("cancel"),
        target: event.composedPath()[0]?.tagName?.toLowerCase() ?? null,
      });
    }, { capture: true });
    Object.defineProperty(window, "__xenorepoInputEvidence", { value: records });
  }, { schemaVersion: EVIDENCE_SCHEMA_VERSION });
}

async function readInputEvidence(page) {
  return page.evaluate(() => window.__xenorepoInputEvidence || []);
}

function validateInputEvidence(records, claim) {
  const trusted = records.filter(record => record.trusted);
  const reject = reason => ({ accepted: false, reason, records });
  if (!trusted.length) return reject("EVIDENCE_UNTRUSTED");
  if (claim === "keyboard") {
    const downs = trusted.filter(record => record.type === "keydown");
    const ups = trusted.filter(record => record.type === "keyup");
    return downs.length && downs.length === ups.length
      ? { accepted: true, records } : reject("EVIDENCE_KEYBOARD_UNBALANCED");
  }
  const pointerType = claim === "touch" ? "touch" : "mouse";
  const pointer = trusted.filter(record => record.pointerType === pointerType);
  if (pointer.some(record => record.canceled)) return reject("EVIDENCE_POINTER_CANCELED");
  const phases = pointer.map(record => record.type);
  if (!phases.includes("pointerdown") || !phases.includes("pointermove")
      || !phases.includes("pointerup")) return reject("EVIDENCE_POINTER_INCOMPLETE");
  const ids = new Set(pointer.map(record => record.pointerId));
  if (ids.size !== 1) return reject("EVIDENCE_POINTER_IDENTITY");
  return { accepted: true, records };
}

/** Domain-neutral fixture which records browser failures and same-origin violations. */
const test = base.extend({
  _browserAudit: [async ({ page }, use) => {
    const failures = [];
    const origin = new URL(base.info().project.use.baseURL || page.url()).origin;
    page.on("console", message => {
      if (message.type() === "error" && !message.text().startsWith("Failed to load resource:")) {
        failures.push(`console: ${message.text()}`);
      }
    });
    page.on("pageerror", error => failures.push(`page: ${error.message}`));
    page.on("requestfailed", request => {
      const reason = request.failure()?.errorText || "unknown";
      if (reason !== "net::ERR_ABORTED") failures.push(`request: ${request.url()} (${reason})`);
    });
    page.on("request", request => {
      if (["http:", "https:"].includes(new URL(request.url()).protocol)
          && new URL(request.url()).origin !== origin) failures.push(`external-origin: ${request.url()}`);
    });
    page.on("response", response => {
      if (response.status() >= 400
          && !acknowledgedHttpStatuses.get(page)?.has(response.status())) {
        failures.push(`http: ${response.status()} ${response.url()}`);
      }
    });
    await use();
    expect(failures, failures.join("\n")).toEqual([]);
  }, { auto: true }],
  auditedPage: async ({ page }, use) => {
    await installInputEvidence(page);
    await use(page);
  },
});

async function mousePath(page, points) {
  if (points.length < 2) throw new Error("mousePath requires at least two coordinates");
  await page.mouse.move(points[0].x, points[0].y);
  await page.mouse.down();
  for (const point of points.slice(1)) await page.mouse.move(point.x, point.y, { steps: 2 });
  await page.mouse.up();
}

async function touchPath(page, points, pointerId = 1) {
  if (points.length < 2) throw new Error("touchPath requires at least two coordinates");
  const session = await page.context().newCDPSession(page);
  await session.send("Input.dispatchTouchEvent", {
    type: "touchStart", touchPoints: [{ ...points[0], id: pointerId }],
  });
  for (const point of points.slice(1)) {
    await session.send("Input.dispatchTouchEvent", {
      type: "touchMove", touchPoints: [{ ...point, id: pointerId }],
    });
  }
  await session.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
}

async function keyboardSequence(page, keys) {
  for (const key of keys) {
    await page.keyboard.down(key);
    await page.keyboard.up(key);
  }
}

module.exports = {
  EVIDENCE_SCHEMA_VERSION, acknowledgeHttpFailures, expect, installInputEvidence,
  keyboardSequence, mousePath,
  readInputEvidence, test, touchPath, validateInputEvidence,
};
