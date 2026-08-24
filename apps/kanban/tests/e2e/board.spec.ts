import { expect, test } from "@playwright/test";

test("a card can be created, dragged, deleted, undone, and redone", async ({ page }, testInfo) => {
  await page.goto("/");

  await expect(page.getByText("KANBAN // 01")).toBeVisible();
  await expect(page.locator(".column")).toHaveCount(3);

  const title = `Browser-validated card ${Date.now()}`;
  await page.getByRole("textbox", { name: "New card for To do", exact: true }).fill(title);
  await page.locator("#column-todo").getByRole("button", { name: "ADD", exact: true }).click();

  const card = page.locator(".card").filter({ hasText: title });
  const doingCards = page.locator("#column-doing .cards");
  await expect(card).toBeVisible();
  await expect(page.getByRole("button", { name: "UNDO" })).toBeEnabled();

  if (testInfo.project.name === "mobile-chromium") {
    const handle = card.locator(".drag-handle");
    const destination = await doingCards.boundingBox();
    if (!destination) throw new Error("Doing column has no drag destination");
    await handle.dispatchEvent("pointerdown", { pointerId:7, pointerType:"touch", isPrimary:true });
    await handle.dispatchEvent("pointermove", { pointerId:7, pointerType:"touch", isPrimary:true,
      clientX:destination.x + destination.width / 2, clientY:destination.y + destination.height / 2 });
    await handle.dispatchEvent("pointerup", { pointerId:7, pointerType:"touch", isPrimary:true,
      clientX:destination.x + destination.width / 2, clientY:destination.y + destination.height / 2 });
  } else {
    await card.locator(".drag-handle").dragTo(doingCards);
  }
  await expect(doingCards.locator(".card").filter({ hasText: title })).toBeVisible();

  const deleteButton = card.getByRole("button", { name: "Delete card" });
  const deleteControl = card.locator("x-command-button.delete");
  await expect(deleteControl).toHaveAttribute("appearance", "subtle");
  await expect(deleteControl).toHaveCSS("position", "absolute");
  await expect(deleteButton).toHaveCSS("border-style", "none");
  await expect(deleteButton).toHaveCSS("box-shadow", "none");
  await expect(deleteButton).not.toHaveCSS("text-shadow", "none");
  await deleteButton.click();
  await expect(card).toHaveCount(0);

  await page.getByRole("button", { name: "UNDO" }).click();
  await expect(doingCards.locator(".card").filter({ hasText: title })).toBeVisible();

  await page.getByRole("button", { name: "REDO" }).click();
  await expect(page.locator(".card").filter({ hasText: title })).toHaveCount(0);
});

test("cards can be renamed, precisely ordered, and restored", async ({ page }) => {
  await page.goto("/");
  const marker = Date.now();
  const firstTitle = `First ${marker}`;
  const renamedTitle = `Renamed ${marker}`;
  const secondTitle = `Second ${marker}`;
  const todo = page.locator("#column-todo");
  const doing = page.locator("#column-doing");
  const addTodo = page.getByRole("textbox", { name: "New card for To do", exact: true });

  await addTodo.fill(firstTitle);
  await todo.getByRole("button", { name: "Add" }).click();
  await expect(page.locator(".card").filter({ hasText: firstTitle })).toBeVisible();
  await addTodo.fill(secondTitle);
  await todo.getByRole("button", { name: "Add" }).click();
  await expect(page.locator(".card").filter({ hasText: secondTitle })).toBeVisible();

  const first = page.locator(".card").filter({ hasText: firstTitle });
  await first.click();
  const editor = page.getByRole("textbox", { name: "Card title" });
  await expect(editor).toBeFocused();
  await editor.fill(renamedTitle);
  await editor.press("Enter");
  const renamed = page.locator(".card").filter({ hasText: renamedTitle });
  await expect(page.getByRole("button", { name: "UNDO" })).toHaveAttribute(
    "title",
    `Rename “${firstTitle}” to “${renamedTitle}”`,
  );

  const second = page.locator(".card").filter({ hasText: secondTitle });
  await second.dragTo(renamed, { targetPosition: { x: 10, y: 1 } });
  await expect.poll(async () => {
    const titles = await todo.locator(".card-title").allTextContents();
    return titles.indexOf(secondTitle) < titles.indexOf(renamedTitle);
  }).toBe(true);

  const firstDoingCard = doing.locator(".card").first();
  await renamed.dragTo(firstDoingCard, { targetPosition: { x: 10, y: 1 } });
  await expect(doing.locator(".card").first()).toContainText(renamedTitle);

  await page.getByRole("button", { name: "UNDO" }).click();
  await expect(todo.locator(".card").filter({ hasText: renamedTitle })).toBeVisible();
  await page.getByRole("button", { name: "UNDO" }).click();
  await expect.poll(async () => {
    const titles = await todo.locator(".card-title").allTextContents();
    return titles.indexOf(renamedTitle) < titles.indexOf(secondTitle);
  }).toBe(true);

  await page.getByRole("button", { name: "REDO" }).click();
  await expect.poll(async () => {
    const titles = await todo.locator(".card-title").allTextContents();
    return titles.indexOf(secondTitle) < titles.indexOf(renamedTitle);
  }).toBe(true);
  await page.getByRole("button", { name: "REDO" }).click();
  await expect(doing.locator(".card").first()).toContainText(renamedTitle);
});
