const { expect, test } = require("@xenorepo/browser-testing");

const routes = JSON.parse(process.env.XENOREPO_FRONTEND_ROUTES
  || '[{"path":"/","artifact":"index.html"}]');

for (const route of routes) {
  test(`[browser-integration] declared route ${route.path} renders its self-contained artifact`,
    async ({ auditedPage: page }) => {
      const response = await page.goto(route.path);
      expect(response?.ok(), `HTTP ${response?.status()} for ${route.path}`).toBe(true);
      await expect(page.locator("body")).toBeVisible();
      await expect.poll(async () => page.evaluate(() => {
        const mount = document.querySelector("#app");
        return (mount?.children.length || document.body.children.length) > 0;
      })).toBe(true);
      expect(await page.locator('script[src], link[rel="stylesheet"][href]').count()).toBe(0);
      expect(await page.locator(
        `meta[name="xenorepo-artifact"][content="${route.artifact}"]`).count()).toBe(1);
    });

  test(`[browser-integration] declared route ${route.path} survives a browser reload`,
    async ({ auditedPage: page }) => {
      await page.goto(route.path);
      await expect.poll(async () => page.locator("#app").evaluate(
        mount => mount.children.length)).toBeGreaterThan(0);

      const response = await page.reload();

      expect(response?.ok(), `HTTP ${response?.status()} after reloading ${route.path}`).toBe(true);
      await expect.poll(async () => page.locator("#app").evaluate(
        mount => mount.children.length)).toBeGreaterThan(0);
      expect(await page.locator(
        `meta[name="xenorepo-artifact"][content="${route.artifact}"]`).count()).toBe(1);
    });

  test(`[accessibility] declared route ${route.path} exposes structure and keyboard focus`,
    async ({ auditedPage: page }) => {
      await page.goto(route.path);
      await expect(page).toHaveTitle(/\S/);
      await expect(page.locator("html")).toHaveAttribute("lang", /\S/);
      await expect(page.locator("main:visible")).toHaveCount(1);

      const focusable = page.locator(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), '
        + 'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])');
      expect(await focusable.count(), `no keyboard target on ${route.path}`).toBeGreaterThan(0);
      await page.keyboard.press("Tab");
      await expect.poll(async () => page.evaluate(() => {
        const active = document.activeElement;
        return Boolean(active && active !== document.body && active !== document.documentElement);
      })).toBe(true);
    });
}
