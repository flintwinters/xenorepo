const { expect, test } = require("@xenorepo/browser-testing");

const routes = JSON.parse(process.env.XENOREPO_FRONTEND_ROUTES || '[{"path":"/","artifact":"index.html"}]');
const aestheticDirectory = process.env.XENOREPO_AESTHETIC_SCREENSHOTS;
const aestheticViewports = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "phone", width: 390, height: 844 },
];

function routeName(route) {
  return route === "/" ? "root" : route.replace(/^\/+|\/+$/g, "").replace(/[^a-z0-9]+/gi, "-");
}

async function visualDefects(page) {
  return page.evaluate(() => {
    function elementLabel(element) {
      return (
        element.getAttribute("aria-label") ||
        element.textContent ||
        element.getAttribute("name") ||
        element.tagName
      )
        .trim()
        .slice(0, 50);
    }
    function rendered(element) {
      const style = getComputedStyle(element);
      return style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0;
    }
    function insideHorizontalScroller(element) {
      for (let ancestor = element.parentElement; ancestor; ancestor = ancestor.parentElement) {
        const overflow = getComputedStyle(ancestor).overflowX;
        if ((overflow === "auto" || overflow === "scroll") && ancestor.scrollWidth > ancestor.clientWidth + 1)
          return true;
      }
      return false;
    }
    function targetDefect(element, box, label) {
      if (element.getAttribute("data-ui-control") === "domain") return null;
      const minimum = innerWidth <= 390 ? 28 : 18;
      return box.width < minimum || box.height < minimum
        ? `generic control below ${minimum}px target: ${label}`
        : null;
    }
    function interactiveDefects() {
      const defects = [];
      const interactive = [
        ...document.querySelectorAll(
          'a[href], button, input, select, textarea, [role="button"], [tabindex]:not([tabindex="-1"])',
        ),
      ];
      for (const element of interactive) {
        if (!rendered(element)) continue;
        const box = element.getBoundingClientRect();
        const label = elementLabel(element);
        if (box.width < 1 || box.height < 1) defects.push(`zero-size interactive control: ${label}`);
        const target = targetDefect(element, box, label);
        if (target) defects.push(target);
        const visibleWidth = Math.min(box.right, innerWidth) - Math.max(box.left, 0);
        if (visibleWidth < Math.min(box.width, 8) && !insideHorizontalScroller(element))
          defects.push(`horizontally clipped control: ${label}`);
      }
      return defects;
    }
    function tinyTextDefects() {
      const defects = [];
      for (const element of document.querySelectorAll("body *")) {
        const style = getComputedStyle(element);
        const visible = rendered(element);
        const leafText = element.childElementCount === 0 && element.textContent?.trim();
        if (visible && leafText && Number.parseFloat(style.fontSize) < 10) {
          defects.push(`text below 10px: ${element.textContent.trim().slice(0, 50)}`);
        }
      }
      return defects;
    }
    const root = document.documentElement;
    const defects = [...interactiveDefects(), ...tinyTextDefects()];
    if (root.scrollWidth > root.clientWidth + 1) {
      defects.push(`horizontal overflow: document is ${root.scrollWidth}px wide in a ${root.clientWidth}px viewport`);
    }
    return [...new Set(defects)].slice(0, 20);
  });
}

for (const route of routes) {
  test(`[browser-integration] declared route ${route.path} renders its self-contained artifact`, async ({
    auditedPage: page,
  }) => {
    const response = await page.goto(route.path);
    expect(response?.ok(), `HTTP ${response?.status()} for ${route.path}`).toBe(true);
    await expect(page.locator("body")).toBeVisible();
    await expect
      .poll(async () =>
        page.evaluate(() => {
          const mount = document.querySelector("#app");
          return (mount?.children.length || document.body.children.length) > 0;
        }),
      )
      .toBe(true);
    expect(await page.locator('script[src], link[rel="stylesheet"][href]').count()).toBe(0);
    expect(await page.locator(`meta[name="xenorepo-artifact"][content="${route.artifact}"]`).count()).toBe(1);
  });

  test(`[browser-integration] declared route ${route.path} survives a browser reload`, async ({
    auditedPage: page,
  }) => {
    await page.goto(route.path);
    await expect.poll(async () => page.locator("#app").evaluate((mount) => mount.children.length)).toBeGreaterThan(0);

    const response = await page.reload();

    expect(response?.ok(), `HTTP ${response?.status()} after reloading ${route.path}`).toBe(true);
    await expect.poll(async () => page.locator("#app").evaluate((mount) => mount.children.length)).toBeGreaterThan(0);
    expect(await page.locator(`meta[name="xenorepo-artifact"][content="${route.artifact}"]`).count()).toBe(1);
  });

  test(`[accessibility] declared route ${route.path} exposes structure and keyboard focus`, async ({
    auditedPage: page,
  }) => {
    await page.goto(route.path);
    await expect(page).toHaveTitle(/\S/);
    await expect(page.locator("html")).toHaveAttribute("lang", /\S/);
    await expect(page.locator("main:visible")).toHaveCount(1);

    const focusable = page.locator(
      "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), " +
        'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    expect(await focusable.count(), `no keyboard target on ${route.path}`).toBeGreaterThan(0);
    await page.keyboard.press("Tab");
    await expect
      .poll(async () =>
        page.evaluate(() => {
          const active = document.activeElement;
          return Boolean(active && active !== document.body && active !== document.documentElement);
        }),
      )
      .toBe(true);
  });

  test(`[visual] declared route ${route.path} has sound geometry at review resolutions`, async ({
    auditedPage: page,
  }, testInfo) => {
    test.skip(
      testInfo.project.name !== "wide-viewport-chromium",
      "one deterministic browser captures the resolution matrix",
    );
    expect(aestheticDirectory, "Monotools must provide an aesthetic screenshot directory").toBeTruthy();
    for (const viewport of aestheticViewports) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(route.path);
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      expect(await visualDefects(page), `${route.path} at ${viewport.name}`).toEqual([]);
      const filename = `${routeName(route.path)}--${viewport.name}` + `--${viewport.width}x${viewport.height}.png`;
      await page.screenshot({
        path: `${aestheticDirectory}/${filename}`,
        fullPage: false,
        animations: "disabled",
      });
    }
  });
}
