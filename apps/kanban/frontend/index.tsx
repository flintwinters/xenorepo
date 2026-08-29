/** Durable board interactions composed from central Preact UI primitives. */
import { Component, render } from "preact";
import {
  CommandButton, ConsolePane, ConsoleShell, EmptyState, StatusRail, UtilityRail,
} from "@xenorepo/ui";
import { appendCardNote, changeHistory, createCard, deleteCard, loadBoard, updateCard,
  type Board, type Card, type Column } from "./client.js";
import "./styles.css";

const REVIEW_WINDOW_MS = 24 * 60 * 60 * 1000;
interface State { board: Board | null; message: string; failed: boolean; openCardId: string | null; }
interface Drag {
  card: Card; element: HTMLElement; pointerId: number;
  originX: number; originY: number; active: boolean;
}
interface DropTarget { card?: Card; columnId: string; after?: boolean; }

function StatusIndicator({ label, tone }: { label: string; tone: "green" | "orange" }) {
  const color = tone === "orange" ? "#fe8019" : "#b8bb26";
  return <span class="status-indicator push" style={{ "--indicator": color }}>
    <i /><span role="status">{label}</span>
  </span>;
}

class KanbanBoard extends Component<Record<string, never>, State> {
  override state: State = { board: null, message: "Loading board…", failed: false, openCardId: null };
  private drag: Drag | null = null;
  private suppressCardClick = false;
  private expiryTimer?: number;

  override componentDidMount(): void {
    void this.perform(async () => {
      await this.refresh();
      const count = this.state.board?.cards.length ?? 0;
      this.setState({ message: `${count} active ${count === 1 ? "card" : "cards"} · durable workspace` });
    });
  }
  override componentWillUnmount(): void { window.clearTimeout(this.expiryTimer); }
  private perform = async (action: () => Promise<void>): Promise<void> => {
    try { await action(); this.setState({ failed: false }); }
    catch (error) { this.setState({ failed: true,
      message: error instanceof Error ? error.message : "Unexpected error" }); }
  };
  private refresh = async (): Promise<void> => {
    const board = await loadBoard();
    this.setState({ board }, this.scheduleExpiry);
  };
  private reviewed(card: Card): boolean {
    return card.reviewed_at_ms != null && Date.now() - card.reviewed_at_ms < REVIEW_WINDOW_MS;
  }
  private scheduleExpiry = (): void => {
    window.clearTimeout(this.expiryTimer);
    const expiries = this.state.board?.cards.filter((card) => this.reviewed(card))
      .map((card) => card.reviewed_at_ms! + REVIEW_WINDOW_MS) ?? [];
    if (!expiries.length) return;
    const delay = Math.max(0, Math.min(...expiries) - Date.now());
    this.expiryTimer = window.setTimeout(() => this.forceUpdate(this.scheduleExpiry),
      Math.min(delay + 1, 2_147_483_647));
  };
  private cards(columnId: string): Card[] {
    return this.state.board?.cards.filter((card) => card.column_id === columnId) ?? [];
  }
  private clearTargets(): void {
    document.querySelectorAll(".insert-before,.insert-after,.drop-target")
      .forEach((target) => target.classList.remove("insert-before", "insert-after", "drop-target"));
  }
  private pointerStart(event: PointerEvent, card: Card): void {
    const target = event.target as Element;
    if (!event.isPrimary || event.button !== 0 || target.closest(".x-ui-command,input")
      || (event.pointerType !== "mouse" && !target.closest(".drag-handle"))) return;
    const element = event.currentTarget as HTMLElement;
    this.drag = { card, element, pointerId: event.pointerId, originX: event.clientX,
      originY: event.clientY, active: false };
    try { element.setPointerCapture(event.pointerId); } catch { /* Synthetic checks have no active OS pointer. */ }
  }
  private pointerMove = (event: PointerEvent): void => {
    const drag = this.drag;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (!drag.active && Math.hypot(event.clientX - drag.originX, event.clientY - drag.originY) < 5) return;
    event.preventDefault();
    if (!drag.active) { drag.active = true; drag.element.classList.add("dragging"); }
    this.showPointerTarget(event.clientX, event.clientY);
  };
  private pointerEnd = (event: PointerEvent): void => {
    const drag = this.drag;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (!drag.active) { this.finishPointerDrag(); return; }
    event.preventDefault();
    const target = this.pointerTarget(event.clientX, event.clientY);
    this.suppressCardClick = true;
    window.setTimeout(() => { this.suppressCardClick = false; }, 0);
    this.finishPointerDrag();
    if (!target) return;
    if (target.card) this.moveRelative(drag.card, target.card, Boolean(target.after));
    else void this.move(drag.card, target.columnId);
  };
  private pointerCancel = (event: PointerEvent): void => {
    if (this.drag?.pointerId === event.pointerId) this.finishPointerDrag();
  };
  private pointerTarget(x: number, y: number): DropTarget | null {
    const element = document.elementFromPoint(x, y) as HTMLElement | null;
    const cardElement = element?.closest<HTMLElement>(".card");
    if (cardElement) {
      const card = this.state.board?.cards.find((item) => item.id === cardElement.dataset.cardId);
      if (card) return { card, columnId: card.column_id,
        after: y >= cardElement.getBoundingClientRect().top + cardElement.offsetHeight / 2 };
    }
    const column = element?.closest<HTMLElement>(".cards");
    return column?.dataset.columnId ? { columnId: column.dataset.columnId } : null;
  }
  private showPointerTarget(x: number, y: number): void {
    this.clearTargets();
    const target = this.pointerTarget(x, y);
    if (!target) return;
    if (target.card) document.querySelector<HTMLElement>(`[data-card-id="${target.card.id}"]`)
      ?.classList.add(target.after ? "insert-after" : "insert-before");
    else document.querySelector<HTMLElement>(`.cards[data-column-id="${target.columnId}"]`)
      ?.classList.add("drop-target");
  }
  private finishPointerDrag(): void {
    this.drag?.element.classList.remove("dragging"); this.drag = null; this.clearTargets();
  }
  private moveRelative(dragged: Card, destination: Card, after: boolean): void {
    const cards = this.cards(destination.column_id);
    let index = cards.findIndex((card) => card.id === destination.id) + Number(after);
    const source = cards.findIndex((card) => card.id === dragged.id);
    if (source >= 0 && source < index) index -= 1;
    void this.move(dragged, destination.column_id, index);
  }
  private async move(card: Card, columnId: string, index?: number): Promise<void> {
    const destination = this.state.board!.columns.find((column) => column.id === columnId)!;
    await this.perform(async () => {
      await updateCard(card.id, { column_id: columnId, ...(index === undefined ? {} : { index }) });
      await this.refresh(); this.setState({ message: `Moved “${card.title}” to ${destination.title}` });
    });
  }
  private add = (event: SubmitEvent, column: Column): void => {
    event.preventDefault();
    const input = (event.currentTarget as HTMLFormElement).elements.namedItem("title") as HTMLInputElement;
    const title = input.value.trim();
    if (!title) return;
    void this.perform(async () => {
      const card = await createCard({ title, column_id: column.id });
      await this.refresh(); input.value = "";
      this.setState({ message: `Added “${card.title}” to ${column.title}` });
    });
  };
  private removeCard = async (card: Card): Promise<void> => {
    await this.perform(async () => {
      await deleteCard(card.id); await this.refresh();
      this.setState((state) => ({ openCardId: state.openCardId === card.id ? null : state.openCardId,
        message: `Deleted “${card.title}”` }));
    });
  };
  private setReviewed = async (card: Card, reviewed: boolean): Promise<void> => {
    await this.perform(async () => {
      await updateCard(card.id, { reviewed }); await this.refresh();
      this.setState({ message: `${reviewed ? "Reviewed" : "Reset review for"} “${card.title}”` });
    });
  };
  private appendNote = (event: SubmitEvent, card: Card): void => {
    event.preventDefault();
    const input = (event.currentTarget as HTMLFormElement).elements.namedItem("note") as HTMLTextAreaElement;
    const body = input.value.trim();
    if (!body) return;
    void this.perform(async () => {
      await appendCardNote(card.id, body); await this.refresh(); input.value = "";
      this.setState({ message: `Logged note on “${card.title}”` });
    });
  };
  private history = async (path: "undo" | "redo"): Promise<void> => {
    await this.perform(async () => {
      const board = await changeHistory(path);
      this.setState({ board, message: `${path === "undo" ? "Undid" : "Redid"} the board operation` },
        this.scheduleExpiry);
    });
  };
  private cardClick(event: MouseEvent, card: Card): void {
    if (this.suppressCardClick) { this.suppressCardClick = false; return; }
    if (!(event.target as Element).closest(".x-ui-command,.drag-handle,input"))
      this.setState({ openCardId: card.id });
  }
  private renderCard(card: Card) {
    const reviewed = this.reviewed(card);
    return <article key={card.id} class={`card${reviewed ? "" : " needs-review"}`} data-card-id={card.id}
      onClick={(event) => this.cardClick(event, card)} onPointerDown={(event) => this.pointerStart(event, card)}
      onPointerMove={this.pointerMove} onPointerUp={this.pointerEnd} onPointerCancel={this.pointerCancel}>
      <button class="drag-handle" type="button" title="Drag to move card" aria-label={`Drag ${card.title}`}>⠿</button>
      <input class="review" type="checkbox" aria-label={`Reviewed ${card.title}`}
        title="Checked for 24 hours after review" checked={reviewed} onClick={(event) => event.stopPropagation()}
        onChange={(event) => void this.setReviewed(card, event.currentTarget.checked)} />
      <p class="card-title">{card.title}</p>
      <CommandButton class="delete" appearance="subtle" aria-label="Delete card"
        onClick={() => void this.removeCard(card)}>×</CommandButton>
    </article>;
  }
  private renderColumn(column: Column, index: number) {
    const cards = this.cards(column.id), tones = ["orange", "blue", "green"] as const;
    return <ConsolePane key={column.id} class="column" id={`column-${column.id}`} title={column.title}
      tone={tones[index] ?? "blue"} titleEnd={<span class="count">
        {cards.length} {cards.length === 1 ? "card" : "cards"}
      </span>}>
      <section><form class="add-form" onSubmit={(event) => this.add(event, column)}>
        <label for={`add-${column.id}`}>New card for {column.title}</label>
        <input id={`add-${column.id}`} name="title" maxLength={120} required placeholder="New card title" />
        <CommandButton type="submit">ADD</CommandButton>
      </form><div class="cards" data-column-id={column.id}>
        {cards.length ? cards.map((card) => this.renderCard(card)) : <EmptyState heading="NO CARDS" />}
      </div></section>
    </ConsolePane>;
  }
  private rename = (event: SubmitEvent, card: Card): void => {
    event.preventDefault();
    const input = (event.currentTarget as HTMLFormElement).elements.namedItem("title") as HTMLInputElement;
    const title = input.value.trim();
    if (!title) return;
    this.setState({ openCardId: null });
    void this.perform(async () => {
      if (title === card.title) return;
      await updateCard(card.id, { title }); await this.refresh();
      this.setState({ message: `Renamed “${card.title}” to “${title}”` });
    });
  };
  private renderModal() {
    const card = this.state.board?.cards.find((item) => item.id === this.state.openCardId);
    if (!card) return null;
    const notes = this.state.board?.notes.filter((note) => note.card_id === card.id) ?? [];
    return <div class="modal-backdrop" onClick={(event) => {
      if (event.target === event.currentTarget) this.setState({ openCardId: null });
    }}><section class="modal" role="dialog" aria-modal="true" aria-labelledby="card-modal-title"
      onKeyDown={(event) => { if (event.key === "Escape") this.setState({ openCardId: null }); }}>
      <h2 id="card-modal-title">Edit card</h2>
      <form class="edit-form" onSubmit={(event) => this.rename(event, card)}>
        <input name="title" aria-label="Card title" maxLength={120} required value={card.title} autoFocus />
        <CommandButton type="button" onClick={() => this.setState({ openCardId: null })}>CANCEL</CommandButton>
        <CommandButton type="submit">SAVE</CommandButton>
      </form>
      <h3 class="log-heading">ACTIVITY LOG</h3>
      {notes.length ? <ol class="note-log">{notes.map((note) => <li class="note" key={note.id}>
        <time dateTime={new Date(note.created_at_ms).toISOString()}>
          {new Date(note.created_at_ms).toLocaleString()}
        </time>
        <p>{note.body}</p>
      </li>)}</ol> : <EmptyState heading="NO NOTES" />}
      <form class="note-form" onSubmit={(event) => this.appendNote(event, card)}>
        <textarea name="note" aria-label="New note" maxLength={2000} required />
        <CommandButton type="submit">LOG</CommandButton>
      </form>
    </section></div>;
  }
  override render() {
    const { board, failed, message } = this.state;
    const header = <UtilityRail><strong class="brand">KANBAN // 01</strong>
      <CommandButton title={board?.undo_description ?? "Nothing to undo"} disabled={!board?.can_undo}
        onClick={() => void this.history("undo")}>UNDO</CommandButton>
      <CommandButton title={board?.redo_description ?? "Nothing to redo"} disabled={!board?.can_redo}
        onClick={() => void this.history("redo")}>REDO</CommandButton>
      <span class="context">DELIVERY CONTROL</span>
      <StatusIndicator label={failed ? "ERROR" : "LOCAL"} tone={failed ? "orange" : "green"} />
    </UtilityRail>;
    const footer = <StatusRail class={failed ? "error" : ""}>{message}</StatusRail>;
    return <div class="kanban-console"><ConsoleShell class="kanban-shell" header={header} footer={footer}>
      <section class="board" aria-label="Kanban board">
        {board?.columns.map((column, index) => this.renderColumn(column, index))}
      </section>{this.renderModal()}
    </ConsoleShell></div>;
  }
}

export function mount(root: HTMLElement): void { render(<KanbanBoard />, root); }
