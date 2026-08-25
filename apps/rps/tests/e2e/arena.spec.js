const { expect, test } = require("@xenorepo/browser-testing");

async function onlyManagedService(page) {
  const allowedOrigin = new URL(test.info().project.use.baseURL || process.env.BASE_URL).origin;
  await page.route("**/*", (route) => {
    const requestOrigin = new URL(route.request().url()).origin;
    return requestOrigin === allowedOrigin ? route.continue() : route.abort();
  });
}

test.beforeEach(async ({ page }) => {
  await onlyManagedService(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "ENTER ARENA" })).toBeVisible();
});

test("[acceptance] loads a named player into the arena with accessible throw controls", async ({ page }) => {
  const name = page.getByLabel("DISPLAY NAME");
  const play = page.getByRole("button", { name: "PLAY" });
  await expect(page.locator("#landing > header")).toBeVisible();
  await expect(page.locator("#landing > main")).toBeVisible();
  await expect(name).toBeVisible();
  await expect(play).toBeDisabled();
  await name.fill("Ada");
  await expect(play).toBeEnabled();
  await name.focus();
  await expect(name).toBeFocused();
  await expect(name).toHaveCSS("outline-width", "2px");
  await play.click();
  await expect(page.locator("#arena-view")).toBeVisible();
  await expect(page.getByRole("heading", { name: /THROW CONTROL/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /ROCK/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /PAPER/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /SCISSORS/ })).toBeVisible();
});

test("[acceptance] keeps the landing form usable on a narrow viewport", async ({ page }) => {
  const form = page.locator("#play-form");
  const name = page.getByLabel("DISPLAY NAME");
  const play = page.getByRole("button", { name: "PLAY" });
  await expect(form).toBeVisible();
  await expect(name).toBeInViewport();
  await expect(play).toBeInViewport();
  await name.fill("Lin");
  await expect(play).toBeEnabled();
});
