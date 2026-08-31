import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import { ConsolePane, ConsoleShell, StatusRail, UtilityRail } from "@xenorepo/ui";
import "./styles.css";

type Card = { id: string; title: string; description: string; position: number };
type Column = { id: string; name: string; position: number; cards: Card[] };
type Board = { columns: Column[] };
type CardDraft = { id?: string; columnId: string; title: string; description: string };

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: "Request failed" })) as { error?: string };
    throw new Error(body.error ?? `Request failed (${response.status})`);
  }
  return response.status === 204 ? undefined as T : await response.json() as T;
}

function Application() {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState("");
  const [newColumn, setNewColumn] = useState("");
  const [draft, setDraft] = useState<CardDraft | null>(null);
  const [dragged, setDragged] = useState<string | null>(null);

  const load = async () => {
    try { setBoard(await request<Board>("/api/board")); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Board unavailable"); }
  };
  useEffect(() => { void load(); }, []);

  const mutate = async (path: string, options: RequestInit) => {
    try { await request(path, options); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Change failed"); }
  };
  const createColumn = async (event: SubmitEvent) => {
    event.preventDefault();
    if (!newColumn.trim()) return;
    await mutate("/api/columns", { method: "POST", body: JSON.stringify({ name: newColumn }) });
    setNewColumn("");
  };
  const renameColumn = async (column: Column) => {
    const name = window.prompt("Column name", column.name);
    if (name !== null && name.trim() && name.trim() !== column.name) {
      await mutate(`/api/columns/${column.id}`, {
        method: "PATCH", body: JSON.stringify({ name }),
      });
    }
  };
  const moveColumn = (column: Column, position: number) => mutate(`/api/columns/${column.id}`, {
    method: "PATCH", body: JSON.stringify({ position }),
  });
  const removeColumn = async (column: Column) => {
    if (window.confirm(`Delete empty column “${column.name}”?`)) {
      await mutate(`/api/columns/${column.id}`, { method: "DELETE" });
    }
  };
  const saveCard = async (event: SubmitEvent) => {
    event.preventDefault();
    if (!draft) return;
    const path = draft.id ? `/api/cards/${draft.id}` : "/api/cards";
    const body = draft.id
      ? { title: draft.title, description: draft.description }
      : { column_id: draft.columnId, title: draft.title, description: draft.description };
    await mutate(path, { method: draft.id ? "PATCH" : "POST", body: JSON.stringify(body) });
    setDraft(null);
  };
  const removeCard = async (card: Card) => {
    if (window.confirm(`Delete “${card.title}”?`)) {
      await mutate(`/api/cards/${card.id}`, { method: "DELETE" });
    }
  };
  const dropCard = async (columnId: string, position: number) => {
    if (!dragged) return;
    await mutate(`/api/cards/${dragged}`, {
      method: "PATCH", body: JSON.stringify({ column_id: columnId, position }),
    });
    setDragged(null);
  };

  const header = <UtilityRail><strong>KANBAN // 01</strong><span>LOCAL BOARD</span></UtilityRail>;
  const total = board?.columns.reduce((count, column) => count + column.cards.length, 0) ?? 0;
  const footer = <StatusRail><span>{board ? "SAVED" : "LOADING"}</span><span>{total} CARDS</span></StatusRail>;
  return <ConsoleShell class="app-shell" header={header} footer={footer}>
    <div class="workspace">
      <ConsolePane title="WORKFLOW" tone="green">
        <div class="board-toolbar">
          <div><p class="eyebrow">SINGLE-USER WORKSPACE</p><h1>Move work forward.</h1></div>
          <form onSubmit={createColumn}>
            <label for="new-column">New column</label>
            <div class="inline-control"><input id="new-column" value={newColumn}
              onInput={(event) => setNewColumn(event.currentTarget.value)} maxlength={80}
              placeholder="e.g. Review" required /><button type="submit">Add column</button></div>
          </form>
        </div>
        {error && <p class="error" role="alert">{error}</p>}
        {!board && !error && <p role="status" class="loading">Loading board…</p>}
        {board && <div class="board" aria-label="Kanban board">
          {board.columns.map((column, columnIndex) => <section class="column" key={column.id}
            data-column={column.id} onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => { event.preventDefault(); void dropCard(column.id, column.cards.length); }}>
            <header class="column-header">
              <div><span class="column-index">{String(columnIndex + 1).padStart(2, "0")}</span>
                <h2>{column.name}</h2><span class="count">{column.cards.length}</span></div>
              <div class="column-actions">
                <button aria-label={`Move ${column.name} left`} disabled={columnIndex === 0}
                  onClick={() => void moveColumn(column, columnIndex - 1)}>←</button>
                <button aria-label={`Move ${column.name} right`}
                  disabled={columnIndex === board.columns.length - 1}
                  onClick={() => void moveColumn(column, columnIndex + 1)}>→</button>
                <button aria-label={`Rename ${column.name}`} onClick={() => void renameColumn(column)}>Edit</button>
                <button aria-label={`Delete ${column.name}`} onClick={() => void removeColumn(column)}>×</button>
              </div>
            </header>
            <div class="cards">
              {column.cards.map((card, cardIndex) => <article class="card" key={card.id} draggable
                data-card={card.id} onDragStart={() => setDragged(card.id)}
                onDragEnd={() => setDragged(null)} onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => { event.preventDefault(); event.stopPropagation();
                  void dropCard(column.id, cardIndex); }}>
                <button class="card-body" onClick={() => setDraft({ id: card.id,
                  columnId: column.id, title: card.title, description: card.description })}>
                  <strong>{card.title}</strong>
                  {card.description && <span>{card.description}</span>}
                </button>
                <button class="delete-card" aria-label={`Delete ${card.title}`}
                  onClick={() => void removeCard(card)}>×</button>
              </article>)}
              {column.cards.length === 0 && <p class="empty">DROP WORK HERE</p>}
            </div>
            <button class="add-card" onClick={() => setDraft({ columnId: column.id,
              title: "", description: "" })}>+ Add card</button>
          </section>)}
        </div>}
      </ConsolePane>
      {draft && <div class="modal-backdrop" role="presentation">
        <form class="card-editor" onSubmit={saveCard} aria-label={draft.id ? "Edit card" : "Add card"}>
          <div class="editor-heading"><span>{draft.id ? "EDIT CARD" : "NEW CARD"}</span>
            <button type="button" aria-label="Close editor" onClick={() => setDraft(null)}>×</button></div>
          <label for="card-title">Title</label>
          <input id="card-title" autofocus value={draft.title} maxlength={200} required
            onInput={(event) => setDraft({ ...draft, title: event.currentTarget.value })} />
          <label for="card-description">Description</label>
          <textarea id="card-description" value={draft.description} maxlength={4000} rows={6}
            onInput={(event) => setDraft({ ...draft, description: event.currentTarget.value })} />
          <div class="editor-actions"><button type="button" onClick={() => setDraft(null)}>Cancel</button>
            <button type="submit">Save card</button></div>
        </form>
      </div>}
    </div>
  </ConsoleShell>;
}

export function mount(root: HTMLElement): void { render(<Application />, root); }
