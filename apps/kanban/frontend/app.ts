interface Column {
  id: string;
  title: string;
}

interface Card {
  id: string;
  title: string;
  column_id: string;
}

interface Board {
  columns: Column[];
  cards: Card[];
  can_undo: boolean;
  can_redo: boolean;
  undo_description: string | null;
  redo_description: string | null;
}

const mountPoint = document.querySelector<HTMLElement>("#app");
if (!mountPoint) throw new Error("Application root is missing");
const root: HTMLElement = mountPoint;

let board: Board | null = null;
let message = "Loading board…";
let isError = false;
let openCardId: string | null = null;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}

async function refreshBoard(): Promise<Board> {
  const snapshot = await request<Board>("/api/board");
  board = snapshot;
  return snapshot;
}

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function command(label: string, title: string, action: () => Promise<void>): HTMLButtonElement {
  const button = element("button", "command", label);
  button.type = "button";
  button.title = title;
  button.addEventListener("click", () => void perform(action));
  return button;
}

async function perform(action: () => Promise<void>): Promise<void> {
  try {
    await action();
    isError = false;
  } catch (error) {
    isError = true;
    message = error instanceof Error ? error.message : "Unexpected error";
  }
  render();
}

function renderCard(card: Card): HTMLElement {
  const article = element("article", "card");
  article.dataset.cardId = card.id;
  article.draggable = true;
  article.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.closest(".delete, .drag-handle")) return;
    openCard(card.id);
  });
  article.addEventListener("dragstart", (event) => {
    if (!event.dataTransfer) return;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", card.id);
    article.classList.add("dragging");
    message = `Dragging “${card.title}”`;
  });
  article.addEventListener("dragend", () => {
    article.classList.remove("dragging");
    document.querySelectorAll(".drop-target").forEach((target) => target.classList.remove("drop-target"));
  });
  article.addEventListener("dragover", (event) => {
    event.preventDefault();
    event.stopPropagation();
    clearInsertionTargets();
    const below = event.clientY >= article.getBoundingClientRect().top + article.offsetHeight / 2;
    article.classList.add(below ? "insert-after" : "insert-before");
  });
  article.addEventListener("drop", (event) => {
    event.preventDefault();
    event.stopPropagation();
    const draggedId = event.dataTransfer?.getData("text/plain");
    const dragged = board!.cards.find((candidate) => candidate.id === draggedId);
    if (!dragged) return;
    const destinationCards = board!.cards.filter(
      (candidate) => candidate.column_id === card.column_id,
    );
    const below = article.classList.contains("insert-after");
    let index = destinationCards.findIndex((candidate) => candidate.id === card.id) + Number(below);
    const sourceIndex = destinationCards.findIndex((candidate) => candidate.id === dragged.id);
    if (sourceIndex >= 0 && sourceIndex < index) index -= 1;
    clearInsertionTargets();
    void perform(async () => move(dragged, card.column_id, index));
  });
  const dragHandle = element("span", "drag-handle", "⠿");
  dragHandle.draggable = true;
  dragHandle.title = "Drag to move card";
  dragHandle.setAttribute("aria-hidden", "true");
  article.append(dragHandle);
  const title = element("p", "card-title", card.title);
  article.append(title);
  const actions = element("div", "card-actions");
  const remove = command("×", "Delete card", async () => {
    await request(`/api/cards/${card.id}`, { method: "DELETE" });
    if (openCardId === card.id) openCardId = null;
    await refreshBoard();
    message = `Deleted “${card.title}”`;
  });
  remove.setAttribute("aria-label", "Delete card");
  remove.classList.add("delete");
  actions.append(remove);
  article.append(actions);
  return article;
}

function openCard(cardId: string): void {
  openCardId = cardId;
  render();
  const input = document.querySelector<HTMLInputElement>(".card-modal-input");
  input?.focus();
  input?.select();
}

function renderCardModal(): HTMLElement | null {
  const card = board?.cards.find((candidate) => candidate.id === openCardId);
  if (!card) return null;
  const backdrop = element("div", "modal-backdrop");
  const dialog = element("section", "card-modal");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", "card-modal-title");
  const heading = element("h2", "card-modal-heading", "Edit card");
  heading.id = "card-modal-title";
  const form = element("form", "card-modal-form");
  const input = element("input", "card-modal-input");
  input.value = card.title;
  input.maxLength = 120;
  input.setAttribute("aria-label", "Card title");
  const cancel = element("button", "command", "Cancel");
  cancel.type = "button";
  cancel.addEventListener("click", () => {
    openCardId = null;
    render();
  });
  const save = element("button", "command", "Save");
  save.type = "submit";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const title = input.value.trim();
    if (!title) {
      input.setAttribute("aria-invalid", "true");
      return;
    }
    openCardId = null;
    void perform(async () => {
      if (title !== card.title) {
        await request<Card>(`/api/cards/${card.id}`, {
          method: "PATCH",
          body: JSON.stringify({ title }),
        });
        await refreshBoard();
        message = `Renamed “${card.title}” to “${title}”`;
      }
    });
  });
  input.addEventListener("input", () => input.removeAttribute("aria-invalid"));
  dialog.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    openCardId = null;
    render();
  });
  backdrop.addEventListener("click", (event) => {
    if (event.target !== backdrop) return;
    openCardId = null;
    render();
  });
  form.append(input, cancel, save);
  dialog.append(heading, form);
  backdrop.append(dialog);
  return backdrop;
}

function clearInsertionTargets(): void {
  document.querySelectorAll(".insert-before, .insert-after").forEach((target) => {
    target.classList.remove("insert-before", "insert-after");
  });
}

async function move(card: Card, columnId: string, index?: number): Promise<void> {
  const destination = board!.columns.find((column) => column.id === columnId)!;
  await request<Card>(`/api/cards/${card.id}`, {
    method: "PATCH",
    body: JSON.stringify({ column_id: destination.id, ...(index === undefined ? {} : { index }) }),
  });
  await refreshBoard();
  message = `Moved “${card.title}” to ${destination.title}`;
}

function renderColumn(column: Column, index: number): HTMLElement {
  const section = element("section", "column");
  section.setAttribute("aria-labelledby", `column-${column.id}`);
  const cards = board!.cards.filter((card) => card.column_id === column.id);
  const title = element("header", "pane-title");
  title.id = `column-${column.id}`;
  title.append(
    element("span", "index", String(index + 1).padStart(2, "0")),
    element("span", "", column.title),
    element("span", "count", `${cards.length} ${cards.length === 1 ? "card" : "cards"}`),
  );
  const cardList = element("div", "cards");
  cardList.addEventListener("dragover", (event) => {
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
    cardList.classList.add("drop-target");
    clearInsertionTargets();
  });
  cardList.addEventListener("dragleave", (event) => {
    if (!cardList.contains(event.relatedTarget as Node | null)) cardList.classList.remove("drop-target");
  });
  cardList.addEventListener("drop", (event) => {
    event.preventDefault();
    cardList.classList.remove("drop-target");
    const cardId = event.dataTransfer?.getData("text/plain");
    const card = board!.cards.find((candidate) => candidate.id === cardId);
    if (!card) return;
    void perform(async () => move(card, column.id));
  });
  if (cards.length === 0) cardList.append(element("p", "empty", "No cards in this queue"));
  cards.forEach((card) => cardList.append(renderCard(card)));

  const form = element("form", "add-form");
  const label = element("label", "", `New card for ${column.title}`);
  const input = element("input");
  input.name = "title";
  input.maxLength = 120;
  input.required = true;
  input.placeholder = "New card title";
  label.htmlFor = `add-${column.id}`;
  input.id = `add-${column.id}`;
  const submit = element("button", "command", "Add");
  submit.type = "submit";
  form.append(label, input, submit);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const titleValue = input.value.trim();
    if (!titleValue) return;
    void perform(async () => {
      const card = await request<Card>("/api/cards", {
        method: "POST",
        body: JSON.stringify({ title: titleValue, column_id: column.id }),
      });
      await refreshBoard();
      message = `Added “${card.title}” to ${column.title}`;
    });
  });
  section.append(title, form, cardList);
  return section;
}

function historyCommands(): HTMLButtonElement[] {
  if (!board) return [];
  const undo = command("UNDO", board.undo_description ?? "Nothing to undo", async () => {
    board = await request<Board>("/api/undo", { method: "POST" });
    message = "Undid the last board operation";
  });
  undo.disabled = !board.can_undo;
  const redo = command("REDO", board.redo_description ?? "Nothing to redo", async () => {
    board = await request<Board>("/api/redo", { method: "POST" });
    message = "Redid the next board operation";
  });
  redo.disabled = !board.can_redo;
  return [undo, redo];
}

function render(): void {
  root.replaceChildren();
  const shell = element("div", "shell");
  const utility = element("header", "utility");
  utility.append(element("span", "brand", "KANBAN // 01"), ...historyCommands());
  utility.append(
    element("span", "utility-note", "A minimal delivery console"),
    element("span", isError ? "connection error" : "connection", isError ? "● ERROR" : "● LOCAL"),
  );
  const boardElement = element("section", "board");
  boardElement.setAttribute("aria-label", "Kanban board");
  if (board) board.columns.forEach((column, index) => boardElement.append(renderColumn(column, index)));
  const status = element("footer", `status${isError ? " error" : ""}`, message);
  shell.append(utility, boardElement, status);
  root.append(shell);
  const modal = renderCardModal();
  if (modal) root.append(modal);
}

render();
void perform(async () => {
  const snapshot = await refreshBoard();
  message = `${snapshot.cards.length} active ${snapshot.cards.length === 1 ? "card" : "cards"} · SQLite workspace`;
});
