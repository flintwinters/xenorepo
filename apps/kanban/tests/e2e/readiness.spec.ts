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

test("[acceptance] creates, edits, drags, archives, restores, and reloads durable work",
  async ({ context, page }, testInfo) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await expect(page.getByRole("status")).toHaveText("Board ready");
  const initialBoard = (await (await page.request.get("/api/board")).json()).board;
  const copyButton = page.getByRole("banner").getByRole("button").first();
  await expect(copyButton).toHaveText("COPY JSON");
  await copyButton.click();
  await expect(page.getByRole("status")).toHaveText("Board JSON copied");
  const initialCurrent = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()));
  expect(initialCurrent).toEqual(expect.objectContaining({
    name: initialBoard.name, description: initialBoard.description,
    background_color: initialBoard.background_color, accent_color: initialBoard.accent_color,
    label_colors: initialBoard.label_colors,
  }));
  expect(Object.keys(initialCurrent)).toEqual([
    "name", "description", "background_color", "accent_color", "label_colors",
    "columns", "cards", "logs", "attachments",
  ]);
  expect(initialCurrent).not.toHaveProperty("board");
  expect(initialCurrent.columns.every((value: object) =>
    Object.keys(value).join() === "id,name,color")).toBe(true);
  expect(initialCurrent.cards.every((value: object) => Object.keys(value).join() ===
    "id,column_id,title,labels")).toBe(true);
  expect(initialCurrent.logs.every((value: object) =>
    Object.keys(value).join() === "card_id,body,created_at")).toBe(true);
  expect(initialCurrent.attachments.every((value: object) => Object.keys(value).join() ===
    "card_id,kind,title,url,original_name,media_type")).toBe(true);
  const currentColumnIds = new Set(initialCurrent.columns.map((value: { id: string }) => value.id));
  expect(initialCurrent.cards.every(
    (value: { column_id: string }) => currentColumnIds.has(value.column_id))).toBe(true);
  const currentCardIds = new Set(initialCurrent.cards.map((value: { id: string }) => value.id));
  expect([...initialCurrent.logs, ...initialCurrent.attachments].every(
    (value: { card_id: string }) => currentCardIds.has(value.card_id))).toBe(true);
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
  await page.getByLabel(`Drag ${doing} column`).dragTo(page.getByLabel(`Drag ${queue} column`));
  await expect(page.getByRole("status")).toHaveText("Column moved");
  await expectColumnBefore(page, doing, queue);
  await page.reload();
  await expectColumnBefore(page, doing, queue);
  await page.getByLabel(`Drag ${doing} column`).dragTo(page.getByLabel(`Drag ${queue} column`));
  await expect(page.getByRole("status")).toHaveText("Column moved");
  await page.getByRole("button", { name: `Rename ${queue}` }).click();
  const columnEditor = page.getByRole("dialog", { name: "EDIT COLUMN" });
  await expect(columnEditor).toBeVisible();
  await expect(page.getByLabel(`Drag ${queue} column`)
    .getByRole("button", { name: `Archive ${queue}` })).toHaveCount(0);
  await expect(columnEditor.getByRole("button", { name: "ARCHIVE COLUMN" })).toBeVisible();
  await columnEditor.getByLabel("Column name").fill(renamedQueue);
  await columnEditor.getByLabel("Column color").fill("#fff");
  await columnEditor.getByRole("button", { name: "SAVE", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Column renamed");
  const source = page.locator(".column").filter({ hasText: renamedQueue });
  await expect(source.locator(".x-ui-chrome")).toHaveCSS("color", "rgb(29, 32, 33)");
  await page.getByRole("button", { name: "EDIT BOARD" }).click();
  const settings = page.getByRole("dialog", { name: "BOARD SETTINGS" });
  expect(await settings.evaluate((element) => ({
    modalRadius: getComputedStyle(element).borderRadius,
    resize: getComputedStyle(element.querySelector("textarea")!).resize,
    textareaRadius: getComputedStyle(element.querySelector("textarea")!).borderRadius,
  }))).toEqual({ modalRadius: "4px", resize: "none", textareaRadius: "4px" });
  await expect(settings.getByLabel("Board background")).toHaveCount(0);
  await expect(settings.getByLabel("Accent color")).toHaveCount(0);
  await expect(settings.getByLabel("Priority")).toHaveCount(0);
  await settings.getByRole("button", { name: "SAVE", exact: true }).click();
  await expect(page.getByRole("banner").locator(".x-ui-rail"))
    .toHaveCSS("border-bottom-color", "rgb(16, 17, 18)");
  await expect(page.locator(".workspace")).toHaveCSS("background-color", "rgb(29, 32, 33)");
  await source.getByRole("button", { name: "+ CARD" }).click();
  await page.getByLabel("Title").fill(`Prove board ${suffix}`);
  await expect(page.getByLabel("Description")).toHaveCount(0);
  await expect(page.getByLabel("Assignee")).toHaveCount(0);
  await expect(page.getByLabel("Priority")).toHaveCount(0);
  await expect(page.getByLabel("Color", { exact: true })).toHaveCount(0);
  await page.getByLabel(/Labels/).fill("acceptance, durable");
  await page.getByRole("button", { name: "SAVE", exact: true }).click();
  const card = page.locator(".card").filter({ hasText: `Prove board ${suffix}` });
  expect(await card.evaluate((element) => ({
    card: getComputedStyle(element).backgroundColor,
    column: getComputedStyle(element).getPropertyValue("--column-color").trim(),
  }))).toEqual({ card: expect.stringContaining("color(srgb"), column: "#fff" });
  await expect(card).toHaveCSS("color", "rgb(235, 219, 178)");
  await expect(card.locator(".card-chrome strong")).toHaveText(`Prove board ${suffix}`);
  expect(await card.evaluate((element) => {
    const cardStyle = getComputedStyle(element), chromeStyle = getComputedStyle(element.querySelector(".card-chrome")!),
      listStyle = getComputedStyle(element.parentElement!);
    return { cardMargin: cardStyle.margin, cardPadding: cardStyle.padding,
      borderBottom: cardStyle.borderBottomWidth, borderLeft: cardStyle.borderLeftWidth,
      chromeBackground: chromeStyle.backgroundImage, chromeBorderBottom: chromeStyle.borderBottomWidth,
      chromeShadow: chromeStyle.boxShadow, radius: cardStyle.borderRadius,
      insetHighlight: cardStyle.boxShadow !== "none", lineHeight: cardStyle.lineHeight,
      listGap: listStyle.gap, listPadding: listStyle.padding };
  })).toEqual({ cardMargin: "0px", cardPadding: "0px", borderBottom: "2px", borderLeft: "1px",
    chromeBackground: expect.stringContaining("linear-gradient"), chromeBorderBottom: "1px",
    chromeShadow: "rgba(0, 0, 0, 0.25) 0px 1px 1px 0px", radius: "2px", insetHighlight: true,
    lineHeight: "13.2px", listGap: "0px", listPadding: "0px" });
  await expect(card).toHaveCSS("cursor", "text");
  await card.click();
  await expect(page.getByRole("dialog", { name: "CARD DETAILS" })).toHaveCount(0);
  await card.getByRole("button", { name: `Edit Prove board ${suffix}` }).click();
  await expect(page.getByRole("dialog", { name: "CARD DETAILS" })).toBeVisible();
  await expect(page.getByLabel("Priority")).toHaveCount(0);
  await page.getByRole("button", { name: "Cancel" }).click();
  await page.getByRole("button", { name: "EDIT BOARD" }).click();
  const palette = page.getByRole("dialog", { name: "BOARD SETTINGS" });
  const labelColor = palette.locator("section").filter({ hasText: "acceptance" });
  await expect(labelColor.getByRole("heading", { name: "Label “acceptance”" })).toBeVisible();
  const labelColorInput = labelColor.getByLabel("Label color", { exact: true });
  await labelColorInput.fill("#85a");
  await expect(labelColor.locator(".x-ui-color-preview")).toHaveCSS("background-color", "rgb(136, 85, 170)");
  await labelColor.getByRole("button", { name: "SAVE COLOR" }).click();
  await expect(card.locator(".card-badges > span", { hasText: "acceptance" }).filter({ hasText: /^acceptance$/ }))
    .toHaveCSS("color", "rgb(251, 241, 199)");
  const cardId = await card.getAttribute("data-card-id");
  const sourceId = await source.locator(".card-list").getAttribute("data-column");
  const target = page.locator(".column").filter({ hasText: doing }).locator(".card-list");
  const targetId = await target.getAttribute("data-column");
  if (testInfo.project.name === "wide-viewport-chromium") {
    await target.scrollIntoViewIfNeeded();
    await card.locator(".card-chrome").dragTo(target);
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
  const movedCard = target.locator(".card").filter({ hasText: `Prove board ${suffix}` });
  expect(await movedCard.evaluate((element) =>
    getComputedStyle(element).getPropertyValue("--column-color").trim())).toBe("#665c54");
  await movedCard.getByRole("button", { name: `Edit Prove board ${suffix}` }).click();
  await page.getByLabel("Log entry").fill("A persisted acceptance log");
  await page.getByRole("button", { name: "ADD LOG" }).click();
  const itemLog = page.locator(".item-log");
  await expect(itemLog).toContainText("A persisted acceptance log");
  await expect(itemLog.locator("time").first()).toHaveAttribute("datetime", /.+/);
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
  await expect(movedCard.locator(".card-log")).toContainText("A persisted acceptance log");
  await expect(movedCard.locator(".card-log time")).toHaveAttribute("datetime", /.+/);
  await page.reload();
  await expect(target.locator(".card").filter({ hasText: `Prove board ${suffix}` })).toBeVisible();
  await target.locator(".card").filter({ hasText: `Prove board ${suffix}` })
    .getByRole("button", { name: `Edit Prove board ${suffix}` }).click();
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
  await page.getByRole("button", { name: "BOARD", exact: true }).click();
  await source.getByRole("button", { name: `Rename ${renamedQueue}` }).click();
  await page.getByRole("dialog", { name: "EDIT COLUMN" })
    .getByRole("button", { name: "ARCHIVE COLUMN" }).click();
  await expect(page.getByRole("status")).toHaveText("column archived");
  await expect(source).toHaveCount(0);
  expect((await page.request.delete(`/api/archive/column/${targetId}`)).ok()).toBe(true);
  await copyButton.click();
  const current = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()));
  expect(current).not.toHaveProperty("board");
  expect(current.columns.map((value: { id: string }) => value.id)).not.toContain(sourceId);
  expect(current.cards.map((value: { id: string }) => value.id)).not.toContain(cardId);
  expect(current.attachments.some((value: { card_id: string }) => value.card_id === cardId)).toBe(false);
  await page.getByRole("button", { name: "IMPORT JSON" }).click();
  const importDialog = page.getByRole("dialog", { name: "IMPORT JSON" });
  await importDialog.getByLabel("Import mode").selectOption("replace");
  await importDialog.getByLabel("JSON file").setInputFiles({
    name: "board.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(initialCurrent)),
  });
  await importDialog.getByRole("button", { name: "IMPORT", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Replaced board JSON");
  await page.getByRole("button", { name: "IMPORT JSON" }).click();
  const appendDialog = page.getByRole("dialog", { name: "IMPORT JSON" });
  await expect(appendDialog.getByLabel("Import mode")).toHaveValue("append");
  await appendDialog.getByLabel("JSON file").setInputFiles({ name: "empty.json",
    mimeType: "application/json", buffer: Buffer.from(JSON.stringify({
      ...initialCurrent, name: "Ignored append settings", columns: [], cards: [], logs: [],
      attachments: [],
    })) });
  await appendDialog.getByRole("button", { name: "IMPORT", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Appended board JSON");
  await expect(page.getByRole("banner")).toContainText(initialBoard.name);
  expect((await page.request.patch("/api/board", { data: {
    name: initialBoard.name, description: initialBoard.description,
    background_color: initialBoard.background_color, accent_color: initialBoard.accent_color,
    label_colors: initialBoard.label_colors,
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
    await expect(page.getByLabel("Description")).toHaveCount(0);
    await expect(page.getByLabel("Assignee")).toHaveCount(0);
    await page.getByLabel(/Labels/).fill("planning, release");
    await page.getByRole("button", { name: "SAVE", exact: true }).click();
  }
  await expect(page.locator(".card").filter({ hasText: "Outline launch" })).toBeVisible();
  expect(await page.locator(".board").evaluate((board) => {
    const boardBox = board.getBoundingClientRect();
    const columns = [...board.querySelectorAll(".column")].map(
      (column) => column.getBoundingClientRect(),
    );
    return {
      fillsWidth: Math.abs(boardBox.width - board.parentElement!.getBoundingClientRect().width) < 1,
      columnsInside: columns.every((column) =>
        column.left >= boardBox.left && column.right <= boardBox.right + 1),
      equalWidths: Math.max(...columns.map((column) => column.width)) -
        Math.min(...columns.map((column) => column.width)) < 1,
      pageOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    };
  })).toEqual({ fillsWidth: true, columnsInside: true, equalWidths: true, pageOverflow: false });
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important}" });
  await expect(page.locator("#app")).toHaveScreenshot("kanban-board.png", { maxDiffPixels: 500 });
});
