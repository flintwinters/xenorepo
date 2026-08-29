import { type Locator, type Page } from "@playwright/test";
import {
  expect,
  installInputEvidence,
  readInputEvidence,
  test,
  touchPath,
  validateInputEvidence,
} from "@xenorepo/browser-testing";

async function dragWithMouse(
  page: Page,
  source: Locator,
  target: Locator,
  targetPosition?: { x: number; y: number },
): Promise<void> {
  const sourceBox = await source.boundingBox();
  const targetBox = await target.boundingBox();
  if (!sourceBox || !targetBox) throw new Error("Drag source or destination has no bounds");
  await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    targetBox.x + (targetPosition?.x ?? targetBox.width / 2),
    targetBox.y + (targetPosition?.y ?? targetBox.height / 2),
    { steps: 5 },
  );
  await page.mouse.up();
}

test("[acceptance] a card can be created, dragged, deleted, undone, and redone", async ({ page }, testInfo) => {
  await installInputEvidence(page);
  await page.clock.install();
  await page.goto("/");

  await expect(page.getByText("KANBAN // 01")).toBeVisible();
  await expect(page.locator(".column")).toHaveCount(3);

  const title = `Browser-validated card ${Date.now()}`;
  await page.getByRole("textbox", { name: "New card for To do", exact: true }).fill(title);
  await page.locator("#column-todo").getByRole("button", { name: "ADD", exact: true }).click();

  const card = page.locator(".card").filter({ hasText: title });
  const doingCards = page.locator("#column-doing .cards");
  await expect(card).toBeVisible();
  await expect(card).toHaveClass(/needs-review/);
  const review = card.getByRole("checkbox", { name: `Reviewed ${title}` });
  await expect(review).not.toBeChecked();
  await review.check();
  await expect(review).toBeChecked();
  await expect(card).not.toHaveClass(/needs-review/);
  const reviewedBoard = await page.request.get("/api/board");
  const reviewedCard = (await reviewedBoard.json()).cards.find((candidate: any) => candidate.title === title);
  expect(reviewedCard.reviewed_at_ms).toEqual(expect.any(Number));
  const noteText = `Observed at ${Date.now()}`;
  await card.click();
  await page.getByRole("textbox", { name: "New note" }).fill(noteText);
  await page.getByRole("button", { name: "LOG", exact: true }).click();
  const loggedNote = page.locator(".note").filter({ hasText: noteText });
  await expect(loggedNote).toBeVisible();
  await expect(loggedNote.locator("time")).toHaveAttribute("datetime", /T/);
  await page.getByRole("button", { name: "CANCEL", exact: true }).click();
  await page.clock.fastForward(24 * 60 * 60 * 1000 + 1);
  await expect(review).not.toBeChecked();
  await expect(card).toHaveClass(/needs-review/);
  await expect(page.getByRole("button", { name: "UNDO" })).toBeEnabled();

  const modality = testInfo.project.name === "narrow-viewport-chromium" ? "touch" : "mouse";
  if (modality === "touch") {
    const handle = card.locator(".drag-handle");
    const source = await handle.boundingBox();
    const destination = await doingCards.boundingBox();
    if (!source || !destination) throw new Error("Card drag path has no bounds");
    await touchPath(page, [
      { x: source.x + source.width / 2, y: source.y + source.height / 2 },
      { x: source.x + source.width / 2 + 20, y: source.y + source.height / 2 },
      { x: destination.x + destination.width / 2, y: destination.y + destination.height / 2 },
    ]);
  } else {
    await dragWithMouse(page, card.getByRole("button", { name: `Drag ${title}` }), doingCards);
  }
  await expect(doingCards.locator(".card").filter({ hasText: title })).toBeVisible();
  const inputEvidence = await readInputEvidence(page);
  expect(validateInputEvidence(inputEvidence, modality)).toMatchObject({ accepted: true });
  await testInfo.attach("input-evidence.json", {
    body: JSON.stringify({ schemaVersion: 1, modality, records: inputEvidence }, null, 2),
    contentType: "application/json",
  });
  const authoritative = await page.request.get("/api/board");
  expect(authoritative.ok()).toBe(true);
  expect(
    (await authoritative.json()).cards.some(
      (candidate: any) => candidate.column_id === "doing" && candidate.title === title,
    ),
  ).toBe(true);
  await page.reload();
  await expect(doingCards.locator(".card").filter({ hasText: title })).toBeVisible();
  await card.click();
  await expect(page.locator(".note").filter({ hasText: noteText })).toBeVisible();
  await page.getByRole("button", { name: "CANCEL", exact: true }).click();

  const deleteButton = card.getByRole("button", { name: "Delete card" });
  const deleteControl = card.locator(".x-ui-command.delete");
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

test("[visual] initial board console", async ({ page }) => {
  await page.goto("/");
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("board-console.png", { maxDiffPixels: 1500 });
});

test("[acceptance] cards can be renamed, precisely ordered, and restored", async ({ page }) => {
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
  await dragWithMouse(page, second.getByRole("button", { name: `Drag ${secondTitle}` }), renamed, { x: 10, y: 1 });
  await expect
    .poll(async () => {
      const titles = await todo.locator(".card-title").allTextContents();
      return titles.indexOf(secondTitle) < titles.indexOf(renamedTitle);
    })
    .toBe(true);

  const firstDoingCard = doing.locator(".card").first();
  await dragWithMouse(page, renamed.getByRole("button", { name: `Drag ${renamedTitle}` }), firstDoingCard, {
    x: 10,
    y: 1,
  });
  await expect(doing.locator(".card").first()).toContainText(renamedTitle);

  await page.getByRole("button", { name: "UNDO" }).click();
  await expect(todo.locator(".card").filter({ hasText: renamedTitle })).toBeVisible();
  await page.getByRole("button", { name: "UNDO" }).click();
  await expect
    .poll(async () => {
      const titles = await todo.locator(".card-title").allTextContents();
      return titles.indexOf(renamedTitle) < titles.indexOf(secondTitle);
    })
    .toBe(true);

  await page.getByRole("button", { name: "REDO" }).click();
  await expect
    .poll(async () => {
      const titles = await todo.locator(".card-title").allTextContents();
      return titles.indexOf(secondTitle) < titles.indexOf(renamedTitle);
    })
    .toBe(true);
  await page.getByRole("button", { name: "REDO" }).click();
  await expect(doing.locator(".card").first()).toContainText(renamedTitle);
});
