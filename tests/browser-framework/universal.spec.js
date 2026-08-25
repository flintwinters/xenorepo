const { expect, test } = require("@xenorepo/browser-testing");

const routes = JSON.parse(process.env.XENOREPO_FRONTEND_ROUTES
  || '[{"path":"/","artifact":"index.html"}]');

for (const route of routes) {
  test(`[acceptance] declared route ${route.path} renders its self-contained artifact`,
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
}
