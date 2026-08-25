"use strict";

const { expect, test: base } = require("@playwright/test");

/** Domain-neutral fixture which records browser failures and same-origin violations. */
const test = base.extend({
  auditedPage: async ({ page }, use) => {
    const failures = [];
    const origin = new URL(base.info().project.use.baseURL).origin;
    page.on("console", message => {
      if (message.type() === "error") failures.push(`console: ${message.text()}`);
    });
    page.on("pageerror", error => failures.push(`page: ${error.message}`));
    page.on("requestfailed", request => failures.push(`request: ${request.url()}`));
    page.on("request", request => {
      if (new URL(request.url()).origin !== origin) failures.push(`external-origin: ${request.url()}`);
    });
    await use(page);
    expect(failures, failures.join("\n")).toEqual([]);
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

module.exports = { expect, keyboardSequence, mousePath, test, touchPath };
