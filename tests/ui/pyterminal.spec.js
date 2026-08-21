const { expect, test } = require("@playwright/test");

test("presents a responsive terminal while the browser runtime boots", async ({ page }) => {
  await page.route("https://cdn.jsdelivr.net/**", route => route.abort());
  await page.goto("/");

  await expect(page.getByText("PY/WEB", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Terminal output")).toContainText("BOOTING");
  await expect(page.getByLabel("Python command")).toBeDisabled();
  await expect(page.getByRole("button", { name: "CLEAR" })).toBeVisible();
  await expect(page.getByLabel("Terminal output")).toBeInViewport();
  await expect(page.getByLabel("Python command")).toBeInViewport();
  await expect(page.getByText("LOCAL WORKER", { exact: false })).toBeVisible();
});
