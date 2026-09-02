import type { Page } from "@playwright/test";
import { expect, test } from "@xenorepo/browser-testing";

async function createColumn(page: Page, name: string) {
  await page.getByRole("button", { name: "+ COLUMN" }).click();
  const editor = page.getByRole("dialog", { name: "NEW COLUMN" });
  await editor.getByLabel("Column name").fill(name);
  await editor.getByRole("button", { name: "CREATE" }).click();
  await expect(page.locator(".column").filter({ hasText: name })).toBeVisible();
}

async function expectColumnBefore(page: Page, left: string, right: string) {
  await expect.poll(async () => {
    const names = await page.locator(".column .x-ui-chrome > span:first-child").allTextContents();
    return names.indexOf(left) < names.indexOf(right);
  }).toBe(true);
}

test("[acceptance] creates, edits, drags, archives, restores, and reloads durable work", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("status")).toHaveText("Board ready");
  const initialBoard = (await (await page.request.get("/api/board")).json()).board;
  await page.getByRole("button", { name: "+ COLUMN" }).click();
  await expect(page.getByRole("dialog", { name: "NEW COLUMN" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "NEW COLUMN" })).toHaveCount(0);
  await page.getByRole("button", { name: "+ COLUMN" }).click();
  await page.locator(".backdrop").click({ position: { x: 2, y: 2 } });
  await expect(page.getByRole("dialog", { name: "NEW COLUMN" })).toHaveCount(0);
  const suffix = `${testInfo.project.name}-${Date.now()}`,
    queue = `Queue ${suffix}`, renamedQueue = `Planned ${suffix}`, doing = `Doing ${suffix}`;
  await createColumn(page, queue);
  await createColumn(page, doing);
  await page.getByRole("button", { name: `Rename ${doing}` }).click();
  await page.getByRole("button", { name: `Move ${doing} left` }).click();
  await expect(page.getByRole("status")).toHaveText("Column moved");
  await expectColumnBefore(page, doing, queue);
  await page.reload();
  await expectColumnBefore(page, doing, queue);
  await page.getByRole("button", { name: `Rename ${doing}` }).click();
  await page.getByRole("button", { name: `Move ${doing} right` }).click();
  await expect(page.getByRole("status")).toHaveText("Column moved");
  await page.getByRole("dialog", { name: "EDIT COLUMN" })
    .getByRole("button", { name: "CANCEL" }).click();
  await page.getByRole("button", { name: `Rename ${queue}` }).click();
  const columnEditor = page.getByRole("dialog", { name: "EDIT COLUMN" });
  await expect(columnEditor).toBeVisible();
  await columnEditor.getByLabel("Column name").fill(renamedQueue);
  await columnEditor.getByLabel("Column color").fill("#336699");
  await columnEditor.getByRole("button", { name: "SAVE", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Column renamed");
  const source = page.locator(".column").filter({ hasText: renamedQueue });
  await page.getByRole("button", { name: "EDIT BOARD" }).click();
  const settings = page.getByRole("dialog", { name: "BOARD SETTINGS" });
  expect(await settings.evaluate((element) => ({
    modalRadius: getComputedStyle(element).borderRadius,
    resize: getComputedStyle(element.querySelector("textarea")!).resize,
    textareaRadius: getComputedStyle(element.querySelector("textarea")!).borderRadius,
  }))).toEqual({ modalRadius: "4px", resize: "none", textareaRadius: "4px" });
  await expect(settings.getByLabel("Board background")).toHaveCount(0);
  await expect(settings.getByLabel("Accent color")).toHaveCount(0);
  await settings.getByLabel("Default card priority").selectOption("urgent");
  await settings.getByRole("button", { name: "SAVE", exact: true }).click();
  await expect(page.getByRole("banner").locator(".x-ui-rail"))
    .toHaveCSS("border-bottom-color", "rgb(16, 17, 18)");
  await expect(page.locator(".workspace")).toHaveCSS("background-color", "rgb(29, 32, 33)");
  await source.getByRole("button", { name: "+ CARD" }).click();
  await page.getByLabel("Title").fill(`Prove board ${suffix}`);
  await page.getByLabel("Description").fill("A persisted acceptance card");
  await page.getByLabel("Assignee").fill("Felix");
  await expect(page.getByLabel("Priority")).toHaveValue("urgent");
  await page.getByLabel("Color", { exact: true }).fill("#41395c");
  await page.getByLabel(/Labels/).fill("acceptance, durable");
  await page.getByRole("button", { name: "SAVE", exact: true }).click();
  const card = page.locator(".card").filter({ hasText: `Prove board ${suffix}` });
  await expect(card).toContainText("@Felix");
  expect(await card.evaluate((element) => {
    const cardStyle = getComputedStyle(element), listStyle = getComputedStyle(element.parentElement!);
    return { cardMargin: cardStyle.margin, cardPadding: cardStyle.padding,
      listGap: listStyle.gap, listPadding: listStyle.padding };
  })).toEqual({ cardMargin: "0px", cardPadding: "0px", listGap: "0px", listPadding: "0px" });
  await page.getByRole("button", { name: "EDIT BOARD" }).click();
  const palette = page.getByRole("dialog", { name: "BOARD SETTINGS" });
  await palette.getByLabel("acceptance").fill("#8255aa");
  await palette.getByRole("button", { name: "SAVE", exact: true }).click();
  const cardId = await card.getAttribute("data-card-id");
  const sourceId = await source.locator(".card-list").getAttribute("data-column");
  const target = page.locator(".column").filter({ hasText: doing }).locator(".card-list");
  const targetId = await target.getAttribute("data-column");
  if (testInfo.project.name === "wide-viewport-chromium") {
    await target.scrollIntoViewIfNeeded();
    await card.dragTo(target);
  } else {
    const response = await page.request.put(`/api/cards/${cardId}/position`, {
      data: { column_id: targetId, position: 0 },
    });
    expect(response.ok()).toBe(true);
    await page.reload();
  }
  await expect(page.getByRole("status")).toHaveText(
    testInfo.project.name === "wide-viewport-chromium" ? "Card moved" : "Board ready",
  );
  await target.locator(".card").filter({ hasText: `Prove board ${suffix}` }).click();
  await page.getByLabel("Comment").fill("The drag persisted");
  await page.getByRole("button", { name: "ADD", exact: true }).click();
  await expect(page.getByText("The drag persisted")).toBeVisible();
  await page.locator(".row").filter({ hasText: "The drag persisted" })
    .getByRole("button", { name: "EDIT" }).click();
  const commentEditor = page.getByRole("dialog", { name: "EDIT COMMENT" });
  await commentEditor.getByLabel("Comment").fill("The drag and edit persisted");
  await commentEditor.getByRole("button", { name: "SAVE", exact: true }).click();
  await expect(page.getByText("The drag and edit persisted")).toBeVisible();
  await page.getByLabel("Link title").fill("Reference");
  await page.getByLabel("Web address").fill("https://example.com/kanban");
  await page.getByRole("button", { name: "ADD LINK" }).click();
  await expect(page.getByRole("link", { name: "Reference" })).toBeVisible();
  await page.locator(".row").filter({ hasText: "Reference" })
    .getByRole("button", { name: "EDIT" }).click();
  const attachmentEditor = page.getByRole("dialog", { name: "EDIT ATTACHMENT" });
  await attachmentEditor.getByLabel("Attachment title").fill("Edited reference");
  await attachmentEditor.getByRole("button", { name: "SAVE", exact: true }).click();
  await expect(page.getByRole("link", { name: "Edited reference" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await page.reload();
  await expect(target.locator(".card").filter({ hasText: `Prove board ${suffix}` })).toBeVisible();
  await target.locator(".card").filter({ hasText: `Prove board ${suffix}` }).click();
  await page.locator(".card-dialog .danger button").click();
  await page.getByRole("banner").getByRole("button", { name: "ARCHIVE", exact: true }).click();
  const archived = page.locator(".archive-row").filter({ hasText: `Prove board ${suffix}` });
  await expect(archived).toBeVisible();
  await archived.getByRole("button", { name: "RESTORE" }).click();
  await page.getByRole("button", { name: "BOARD", exact: true }).click();
  await expect(target.locator(".card").filter({ hasText: `Prove board ${suffix}` })).toBeVisible();
  await page.getByRole("button", { name: "ACTIVITY" }).click();
  await expect(page.locator(".activity-list")).toContainText(`Prove board ${suffix}`);
  expect(cardId && sourceId && targetId).toBeTruthy();
  expect((await page.request.delete(`/api/archive/card/${cardId}`)).ok()).toBe(true);
  expect((await page.request.delete(`/api/archive/column/${sourceId}`)).ok()).toBe(true);
  expect((await page.request.delete(`/api/archive/column/${targetId}`)).ok()).toBe(true);
  expect((await page.request.patch("/api/board", { data: {
    name: initialBoard.name, description: initialBoard.description,
    default_priority: initialBoard.default_priority, background_color: initialBoard.background_color,
    accent_color: initialBoard.accent_color, label_colors: initialBoard.label_colors,
  } })).ok()).toBe(true);
});

test("[visual] populated single-board workflow", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".column").filter({ hasText: /^Queue / })).toHaveCount(0);
  if (await page.locator(".column").count() === 0) {
    await createColumn(page, "Ideas");
    await createColumn(page, "In progress");
    await createColumn(page, "Complete");
    await page.locator(".column").filter({ hasText: "Ideas" }).getByRole("button", { name: "+ CARD" }).click();
    await page.getByLabel("Title").fill("Outline launch");
    await page.getByLabel("Description").fill("Turn the release goal into a concrete plan");
    await page.getByLabel("Assignee").fill("Felix");
    await page.getByLabel("Priority").selectOption("high");
    await page.getByLabel(/Labels/).fill("planning, release");
    await page.getByRole("button", { name: "SAVE", exact: true }).click();
  }
  await expect(page.locator(".card").filter({ hasText: "Outline launch" })).toBeVisible();
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("kanban-board.png", { maxDiffPixels: 500 });
});
