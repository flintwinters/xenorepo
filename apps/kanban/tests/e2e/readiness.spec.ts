import { expect, test } from "@xenorepo/browser-testing";

test("[acceptance] walking skeleton reaches its ready state", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status")).toHaveText(
    "Kanban is ready for product behavior.",
  );
});
