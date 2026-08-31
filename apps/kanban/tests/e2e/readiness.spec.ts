import { type Locator, type Page } from "@playwright/test";
import {
  expect, installInputEvidence, mousePath, readInputEvidence, test, validateInputEvidence,
} from "@xenorepo/browser-testing";

async function mouseDrag(page: Page, source: Locator, target: Locator) {
  await source.scrollIntoViewIfNeeded();
  await target.scrollIntoViewIfNeeded();
  const from = await source.boundingBox(), to = await target.boundingBox();
  if (!from || !to) throw new Error("Kanban drag path has no bounds");
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(from.x + from.width / 2 + 14, from.y + from.height / 2, { steps: 2 });
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 8 });
  await page.mouse.up();
}

async function addCard(page: Page, column: Locator, title: string, description = "") {
  await column.getByRole("button", { name: "Add card" }).click();
  await page.getByLabel("Title").fill(title);
  if (description) await page.getByLabel("Description").fill(description);
  await page.getByRole("button", { name: "Save card" }).click();
  await expect(column.locator(".card").filter({ hasText: title })).toBeVisible();
}

async function removePriorTestFacts(page: Page) {
  const response = await page.request.get("/api/board"), board = await response.json();
  for (const column of board.columns) {
    for (const card of column.cards) {
      if (/^(Plan|Build|Test|Ship) \d+$/.test(card.title)) {
        await page.request.delete(`/api/cards/${card.id}`);
      }
    }
  }
  const refreshed = await (await page.request.get("/api/board")).json();
  for (const column of refreshed.columns) {
    if (/^(Review|Verify) \d+$/.test(column.name) && column.cards.length === 0) {
      await page.request.delete(`/api/columns/${column.id}`);
    }
  }
}

test("[acceptance] shapes a board and durably moves real work", async ({ page }, testInfo) => {
  await installInputEvidence(page);
  await page.goto("/");
  await removePriorTestFacts(page);
  await page.reload();
  await expect(page.getByText("KANBAN // 01")).toBeVisible();
  const board = page.getByLabel("Kanban board");
  await expect(board.locator(".column")).toHaveCount(3);
  const stamp = Date.now();
  await page.getByLabel("New column").fill(`Review ${stamp}`);
  await page.getByRole("button", { name: "Add column" }).click();
  await expect(board.locator(".column")).toHaveCount(4);
  const review = board.locator(".column").filter({ hasText: `Review ${stamp}` });
  await review.getByRole("button", { name: /Move .* left/ }).click();
  page.once("dialog", (dialog) => dialog.accept(`Verify ${stamp}`));
  await review.getByRole("button", { name: /Rename/ }).click();
  const first = board.locator(".column").first(), second = board.locator(".column").nth(1);
  const titles = [`Plan ${stamp}`, `Build ${stamp}`, `Test ${stamp}`, `Ship ${stamp}`];
  await addCard(page, first, titles[0], "Define the smallest useful slice");
  await addCard(page, first, titles[1]);
  await addCard(page, first, titles[2]);
  await addCard(page, first, titles[3]);
  const buildCard = first.locator(".card").filter({ hasText: titles[1] });
  await buildCard.locator(".card-body").click();
  await page.getByLabel("Description").fill("Implement the durable board");
  await page.getByRole("button", { name: "Save card" }).click();
  await mouseDrag(page, first.locator(".card").filter({ hasText: titles[3] }),
    first.locator(".card").filter({ hasText: titles[0] }));
  await mouseDrag(page, first.locator(".card").filter({ hasText: titles[1] }), second);
  await expect(second.locator(".card").filter({ hasText: titles[1] })).toBeVisible();
  const evidenceStart = (await readInputEvidence(page)).length;
  await mousePath(page, [{ x: 4, y: 4 }, { x: 18, y: 18 }, { x: 32, y: 20 }]);
  const evidence = (await readInputEvidence(page)).slice(evidenceStart);
  expect(validateInputEvidence(evidence, "mouse"), JSON.stringify(evidence)).toMatchObject({ accepted: true });
  await testInfo.attach("input-evidence.json", {
    body: JSON.stringify({ schemaVersion: 1, modality: "mouse", records: evidence }, null, 2),
    contentType: "application/json",
  });
  const response = await page.request.get("/api/board");
  expect(response.ok()).toBe(true);
  const authoritative = await response.json();
  expect(authoritative.columns.flatMap((column: { cards: { title: string }[] }) =>
    column.cards.map((card) => card.title))).toEqual(expect.arrayContaining(titles));
  await page.reload();
  await expect(page.locator(".card").filter({ hasText: titles[1] })).toContainText(
    "Implement the durable board",
  );
  page.once("dialog", (dialog) => dialog.accept());
  await page.locator(".card").filter({ hasText: titles[2] }).getByRole("button", { name: /Delete/ }).click();
  await expect(page.locator(".card").filter({ hasText: titles[2] })).toHaveCount(0);
  for (const title of [titles[0], titles[1], titles[3]]) {
    page.once("dialog", (dialog) => dialog.accept());
    await page.locator(".card").filter({ hasText: title }).getByRole("button", { name: /Delete/ }).click();
  }
  const emptyReview = board.locator(".column").filter({ hasText: `Verify ${stamp}` });
  page.once("dialog", (dialog) => dialog.accept());
  await emptyReview.getByRole("button", { name: /Delete/ }).click();
  await expect(emptyReview).toHaveCount(0);
});

test("[visual] initial durable workflow", async ({ page }) => {
  await page.goto("/");
  await removePriorTestFacts(page);
  await page.reload();
  await expect(page.getByLabel("Kanban board").locator(".column")).toHaveCount(3);
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("kanban-board.png", { maxDiffPixels: 300 });
});
