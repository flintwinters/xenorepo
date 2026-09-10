import { expect, test } from "@xenorepo/browser-testing";

const contact = { name: "Ada Lovelace", email: "ada@example.test", phone: "+44 20 0000",
  company: "Analytical Engines", job_title: "Programmer", city: "London", tags: ["friend"] };

test.beforeEach(async ({ request }) => {
  for (const query of ["ada@example.test", "grace@example.test", "person-"]) {
    const listing = await request.get(`/api/contacts?q=${encodeURIComponent(query)}&page_size=100`);
    for (const item of (await listing.json()).items) await request.delete(`/api/contacts/${item.id}`);
  }
  await request.post("/api/contacts", { data: contact });
  for (let index = 0; index < 24; index += 1) await request.post("/api/contacts", { data: {
    ...contact, name: `Person ${String(index).padStart(2, "0")}`,
    email: `person-${index}@example.test`, city: index % 2 ? "Boston" : "Austin",
  } });
});

test("[acceptance] directory data drives search, sort, pagination, and CRUD", async ({ page }) => {
  await page.goto("/");
  const table = page.getByRole("table", { name: "Contacts" });
  await expect(table).toContainText("Ada Lovelace");
  const columnWidths = () => table.locator("thead th").evaluateAll((headers) =>
    headers.map((header) => header.getBoundingClientRect().width));
  const initialColumnWidths = await columnWidths();
  await page.getByLabel("Search contacts").fill("Boston");
  await expect(table.locator("tbody tr")).toHaveCount(12);
  expect(await columnWidths()).toEqual(initialColumnWidths);
  await page.getByLabel("Search contacts").fill("");
  await page.getByRole("button", { name: "NEXT" }).click();
  await expect(page.getByText("PAGE 2", { exact: true }).last()).toBeVisible();
  await page.getByLabel("Sort contacts").selectOption("email");
  await page.getByLabel("Reverse sort").click();
  expect(await columnWidths()).toEqual(initialColumnWidths);

  await page.getByRole("button", { name: "+ CONTACT" }).click();
  await page.getByLabel("Name").fill("Grace Hopper");
  await page.getByLabel("Email").fill("grace@example.test");
  await page.getByRole("button", { name: "CREATE" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await page.getByLabel("Search contacts").fill("grace@example.test");
  await expect(table).toContainText("Grace Hopper");
  await page.getByRole("button", { name: "EDIT" }).click();
  await page.getByLabel("Name").fill("Grace Murray Hopper");
  await page.getByRole("button", { name: "SAVE" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(table).toContainText("Grace Murray Hopper");
  await page.getByRole("button", { name: "EDIT" }).click();
  await page.getByLabel("Confirm this destructive action").check();
  await page.getByRole("button", { name: "DELETE" }).click();
  await expect(page.getByText("NO CONTACTS")).toBeVisible();
});

test("[visual] populated directory remains legible", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("table", { name: "Contacts" })).toBeVisible();
  await expect(page).toHaveScreenshot("contact-directory.png", { animations: "disabled" });
});
