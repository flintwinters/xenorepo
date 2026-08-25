/** Durable board interactions composed from central Lit UI primitives. */
import { LitElement, css, html, nothing } from "lit";
import "@xenorepo/lit-ui";

interface Column { id: string; title: string; }
interface Card { id: string; title: string; column_id: string; reviewed_at_ms: number | null; }
interface CardNote { id: string; card_id: string; body: string; created_at_ms: number; }
interface Board {
  columns: Column[]; cards: Card[]; notes: CardNote[]; can_undo: boolean; can_redo: boolean;
  undo_description: string | null; redo_description: string | null;
}

class KanbanBoard extends LitElement {
  private static readonly REVIEW_WINDOW_MS = 24 * 60 * 60 * 1000;
  static properties = {
    board: { state: true }, message: { state: true }, failed: { state: true },
    openCardId: { state: true },
  };
  declare board: Board | null;
  declare message: string;
  declare failed: boolean;
  declare openCardId: string | null;
  private pointerDrag: {
    card: Card; element: HTMLElement; pointerId: number; originX: number; originY: number; active: boolean;
  } | null = null;
  private suppressCardClick = false;
  private expiryTimer: number | null = null;

  constructor() {
    super();
    this.board = null;
    this.message = "Loading board…";
    this.failed = false;
    this.openCardId = null;
  }

  static styles = css`
    :host { display:block; height:100%; color:#ebdbb2; font:12px/1.3 "Courier New",monospace; }
    * { box-sizing:border-box; } x-console-shell { height:100%; }
    .brand { color:#fabd2f; font-weight:bold; letter-spacing:.08em; }
    .push { margin-left:auto; } .board { min-height:0; display:grid; grid-template-columns:repeat(3,minmax(220px,1fr)); gap:1px; background:#121414; }
    x-console-pane { min-width:0; } .column { display:grid; min-height:100%; grid-template-rows:auto minmax(0,1fr); }
    .count { margin-left:auto; color:#1d2021; font-weight:normal; }
    .add-form { display:grid; grid-template-columns:minmax(0,1fr) auto; border-bottom:1px solid #504945; }
    .add-form label { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }
    input,textarea { min-width:0; padding:3px 6px; color:#ebdbb2; font:inherit; background:#181a1b; border:1px solid #665c54; }
    .cards { min-height:0; overflow:auto; } .cards.drop-target { background:#30312d; box-shadow:inset 0 0 0 1px #d79921; }
    .card { position:relative; min-height:34px; padding:8px 30px 7px 50px; border-bottom:1px solid #504945; border-left:2px solid #928374; background:#222526; cursor:grab; user-select:none; }
    .card.needs-review { border-left-color:#fabd2f; background:#3b321f; box-shadow:inset 3px 0 #d79921; }
    .review { position:absolute; top:8px; left:28px; margin:0; accent-color:#b8bb26; cursor:pointer; }
    .card.dragging { opacity:.42; } .card.insert-before { box-shadow:inset 0 2px #fabd2f; } .card.insert-after { box-shadow:inset 0 -2px #fabd2f; }
    .drag-handle { position:absolute; inset:0 auto 0 0; width:24px; padding:0; color:#a89984; font:inherit; background:transparent; border:0; cursor:grab; touch-action:none; user-select:none; }
    .drag-handle:hover,.drag-handle:focus-visible { color:#fabd2f; background:#3c3836; outline:1px solid #fabd2f; outline-offset:-1px; }
    .drag-handle:active,.card.dragging { cursor:grabbing; }
    .card-title { margin:0; overflow-wrap:anywhere; } .delete { position:absolute; top:3px; right:3px; }
    .delete::part(button) { min-width:20px; padding:0; color:#fb8b7d; }
    .modal-backdrop { position:fixed; z-index:10; inset:0; display:grid; place-items:center; padding:16px; background:#000a; }
    .modal { width:min(560px,100%); max-height:min(700px,calc(100vh - 32px)); overflow:auto; padding:14px; border:1px solid #83a598; background:#282828; box-shadow:0 12px 30px #000; }
    .modal h2 { margin:0 0 10px; font-size:13px; }
    .edit-form { display:grid; grid-template-columns:minmax(0,1fr) auto auto; gap:5px; }
    .log-heading { margin:18px 0 6px; color:#83a598; font-size:12px; letter-spacing:.06em; }
    .note-log { display:grid; gap:1px; margin:0 0 6px; padding:0; list-style:none; background:#504945; }
    .note { display:grid; gap:3px; padding:7px; background:#1d2021; }
    .note time { color:#a89984; font-size:10px; } .note p { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; }
    .note-form { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:5px; align-items:end; }
    .note-form textarea { min-height:54px; resize:vertical; }
    .error { color:#fb4934; }
    @media(max-width:720px) { .board { grid-template-columns:1fr; overflow:auto; } x-console-pane { min-height:220px; } .context { display:none; } }
  `;

  connectedCallback(): void {
    super.connectedCallback();
    void this.perform(async () => {
      await this.refresh();
      this.message = `${this.board!.cards.length} active ${this.board!.cards.length === 1 ? "card" : "cards"} · durable workspace`;
    });
  }

  disconnectedCallback(): void {
    if (this.expiryTimer !== null) window.clearTimeout(this.expiryTimer);
    super.disconnectedCallback();
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(path, { ...options,
      headers: { "Content-Type": "application/json", ...options?.headers } });
    if (!response.ok) {
      const failure = await response.json().catch(() => null) as { error?: string; detail?: string } | null;
      throw new Error(failure?.error ?? failure?.detail ?? `Request failed (${response.status})`);
    }
    return response.status === 204 ? undefined as T : response.json() as Promise<T>;
  }

  private async refresh(): Promise<void> {
    this.board = await this.request<Board>("/api/board");
    this.scheduleExpiry();
  }

  private isReviewed(card: Card): boolean {
    return card.reviewed_at_ms !== null &&
      Date.now() - card.reviewed_at_ms < KanbanBoard.REVIEW_WINDOW_MS;
  }

  private scheduleExpiry(): void {
    if (this.expiryTimer !== null) window.clearTimeout(this.expiryTimer);
    const expiries = this.board?.cards.filter(card => this.isReviewed(card))
      .map(card => card.reviewed_at_ms! + KanbanBoard.REVIEW_WINDOW_MS) ?? [];
    if (!expiries.length) { this.expiryTimer = null; return; }
    const delay = Math.max(0, Math.min(...expiries) - Date.now());
    this.expiryTimer = window.setTimeout(() => {
      this.expiryTimer = null;
      this.requestUpdate();
      this.scheduleExpiry();
    }, Math.min(delay + 1, 2_147_483_647));
  }

  private async perform(action: () => Promise<void>): Promise<void> {
    try { await action(); this.failed = false; }
    catch (error) { this.failed = true; this.message = error instanceof Error ? error.message : "Unexpected error"; }
  }

  private cards(columnId: string): Card[] {
    return this.board?.cards.filter(card => card.column_id === columnId) ?? [];
  }

  private notes(cardId: string): CardNote[] {
    return this.board?.notes.filter(note => note.card_id === cardId) ?? [];
  }

  private clearTargets(): void {
    this.renderRoot.querySelectorAll(".insert-before,.insert-after").forEach(target =>
      target.classList.remove("insert-before", "insert-after"));
  }

  private pointerStart(event: PointerEvent, card: Card): void {
    const target = event.target as Element;
    if (!event.isPrimary || event.button !== 0 || target.closest("x-command-button,input") ||
      (event.pointerType !== "mouse" && !target.closest(".drag-handle"))) return;
    const element = event.currentTarget as HTMLElement;
    this.pointerDrag = { card, element, pointerId:event.pointerId,
      originX:event.clientX, originY:event.clientY, active:false };
    try { element.setPointerCapture(event.pointerId); } catch { /* Synthetic checks have no active OS pointer. */ }
  }

  private pointerMove(event: PointerEvent): void {
    const drag = this.pointerDrag;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (!drag.active && Math.hypot(event.clientX - drag.originX, event.clientY - drag.originY) < 5) return;
    event.preventDefault();
    if (!drag.active) { drag.active = true; drag.element.classList.add("dragging"); }
    this.showPointerTarget(event.clientX, event.clientY);
  }

  private pointerEnd(event: PointerEvent): void {
    const drag = this.pointerDrag;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (!drag.active) { this.finishPointerDrag(); return; }
    event.preventDefault();
    const target = this.pointerTarget(event.clientX, event.clientY);
    this.suppressCardClick = true;
    setTimeout(() => { this.suppressCardClick = false; }, 0);
    this.finishPointerDrag();
    if (!target) return;
    if (target.card) {
      this.moveRelative(drag.card, target.card, Boolean(target.after));
    } else {
      void this.move(drag.card, target.columnId);
    }
  }

  private pointerCancel(event: PointerEvent): void {
    if (this.pointerDrag?.pointerId === event.pointerId) this.finishPointerDrag();
  }

  private pointerTarget(x: number, y: number): { card?: Card; columnId: string; after?: boolean } | null {
    const element = (this.renderRoot as ShadowRoot).elementFromPoint(x, y) as HTMLElement | null;
    const cardElement = element?.closest<HTMLElement>(".card");
    if (cardElement) {
      const card = this.board?.cards.find(item => item.id === cardElement.dataset.cardId);
      if (card) return { card, columnId:card.column_id,
        after:y >= cardElement.getBoundingClientRect().top + cardElement.offsetHeight / 2 };
    }
    const column = element?.closest<HTMLElement>(".cards");
    return column?.dataset.columnId ? { columnId:column.dataset.columnId } : null;
  }

  private showPointerTarget(x: number, y: number): void {
    this.clearTargets();
    this.renderRoot.querySelectorAll(".drop-target").forEach(target => target.classList.remove("drop-target"));
    const target = this.pointerTarget(x, y);
    if (!target) return;
    if (target.card) {
      const element = this.renderRoot.querySelector<HTMLElement>(`[data-card-id="${target.card.id}"]`);
      element?.classList.add(target.after ? "insert-after" : "insert-before");
    } else {
      this.renderRoot.querySelector<HTMLElement>(`.cards[data-column-id="${target.columnId}"]`)?.classList.add("drop-target");
    }
  }

  private finishPointerDrag(): void {
    this.pointerDrag?.element.classList.remove("dragging");
    this.pointerDrag = null;
    this.renderRoot.querySelectorAll(".drop-target").forEach(target => target.classList.remove("drop-target"));
    this.clearTargets();
  }

  private moveRelative(dragged: Card, destination: Card, after: boolean): void {
    const cards = this.cards(destination.column_id);
    let index = cards.findIndex(card => card.id === destination.id) + Number(after);
    const source = cards.findIndex(card => card.id === dragged.id);
    if (source >= 0 && source < index) index -= 1;
    void this.move(dragged, destination.column_id, index);
  }

  private async move(card: Card, columnId: string, index?: number): Promise<void> {
    const destination = this.board!.columns.find(column => column.id === columnId)!;
    await this.perform(async () => {
      await this.request(`/api/cards/${card.id}`, { method:"PATCH",
        body:JSON.stringify({ column_id:columnId, ...(index === undefined ? {} : { index }) }) });
      await this.refresh(); this.message = `Moved “${card.title}” to ${destination.title}`;
    });
  }

  private add(event: Event, column: Column): void {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const input = form.elements.namedItem("title") as HTMLInputElement;
    const title = input.value.trim();
    if (!title) return;
    void this.perform(async () => {
      const card = await this.request<Card>("/api/cards", { method:"POST",
        body:JSON.stringify({ title, column_id:column.id }) });
      await this.refresh(); input.value = ""; this.message = `Added “${card.title}” to ${column.title}`;
    });
  }

  private async removeCard(card: Card): Promise<void> {
    await this.perform(async () => {
      await this.request(`/api/cards/${card.id}`, { method:"DELETE" });
      if (this.openCardId === card.id) this.openCardId = null;
      await this.refresh(); this.message = `Deleted “${card.title}”`;
    });
  }

  private async setReviewed(card: Card, reviewed: boolean): Promise<void> {
    await this.perform(async () => {
      await this.request(`/api/cards/${card.id}`, { method:"PATCH",
        body:JSON.stringify({ reviewed }) });
      await this.refresh();
      this.message = `${reviewed ? "Reviewed" : "Reset review for"} “${card.title}”`;
    });
  }

  private appendNote(event: Event, card: Card): void {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const input = form.elements.namedItem("note") as HTMLTextAreaElement;
    const body = input.value.trim();
    if (!body) return;
    void this.perform(async () => {
      await this.request<CardNote>(`/api/cards/${card.id}/notes`, { method:"POST",
        body:JSON.stringify({ body }) });
      await this.refresh();
      input.value = "";
      this.message = `Logged note on “${card.title}”`;
    });
  }

  private async history(path: "undo" | "redo"): Promise<void> {
    await this.perform(async () => {
      this.board = await this.request<Board>(`/api/${path}`, { method:"POST" });
      this.scheduleExpiry();
      this.message = `${path === "undo" ? "Undid" : "Redid"} the board operation`;
    });
  }

  private renderCard(card: Card) {
    const reviewed = this.isReviewed(card);
    return html`<article class=${`card${reviewed ? "" : " needs-review"}`} data-card-id=${card.id} @click=${(event:Event) => {
      if (this.suppressCardClick) { this.suppressCardClick = false; return; }
      if (!(event.target as Element).closest("x-command-button,.drag-handle")) this.openCardId = card.id;
    }} @pointerdown=${(event:PointerEvent) => this.pointerStart(event, card)} @pointermove=${this.pointerMove}
      @pointerup=${this.pointerEnd} @pointercancel=${this.pointerCancel}>
      <button class="drag-handle" type="button" title="Drag to move card"
        aria-label=${`Drag ${card.title}`}>⠿</button>
      <input class="review" type="checkbox" aria-label=${`Reviewed ${card.title}`}
        title="Checked for 24 hours after review" .checked=${reviewed}
        @click=${(event:Event) => event.stopPropagation()}
        @change=${(event:Event) => void this.setReviewed(card, (event.currentTarget as HTMLInputElement).checked)}>
      <p class="card-title">${card.title}</p>
      <x-command-button class="delete" appearance="subtle" label="Delete card" @click=${() => void this.removeCard(card)}>×</x-command-button>
    </article>`;
  }

  private renderColumn(column: Column, index: number) {
    const cards = this.cards(column.id);
    const tones = ["orange", "blue", "green"];
    return html`<x-console-pane class="column" id=${`column-${column.id}`} index=${String(index + 1).padStart(2,"0")}
      title=${column.title} tone=${tones[index]}>
      <span slot="title-end" class="count">${cards.length} ${cards.length === 1 ? "card" : "cards"}</span>
      <section>
        <form class="add-form" @submit=${(event:Event) => this.add(event, column)}>
          <label for=${`add-${column.id}`}>New card for ${column.title}</label>
          <input id=${`add-${column.id}`} name="title" maxlength="120" required placeholder="New card title">
          <x-command-button @click=${(event:Event) => (event.currentTarget as Element).closest("form")?.requestSubmit()}>ADD</x-command-button>
        </form>
        <div class="cards" data-column-id=${column.id}>
          ${cards.length ? cards.map(card => this.renderCard(card)) : html`<x-empty-state heading="NO CARDS"></x-empty-state>`}
        </div>
      </section>
    </x-console-pane>`;
  }

  private renderModal() {
    const card = this.board?.cards.find(item => item.id === this.openCardId);
    if (!card) return nothing;
    const notes = this.notes(card.id);
    return html`<div class="modal-backdrop" @click=${(event:Event) => { if (event.target === event.currentTarget) this.openCardId = null; }}>
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="card-modal-title" @keydown=${(event:KeyboardEvent) => { if (event.key === "Escape") this.openCardId = null; }}>
        <h2 id="card-modal-title">Edit card</h2>
        <form class="edit-form" @submit=${(event:Event) => { event.preventDefault(); const input=(event.currentTarget as HTMLFormElement).elements.namedItem("title") as HTMLInputElement; const title=input.value.trim(); if (!title) return; this.openCardId=null; void this.perform(async()=>{ if(title!==card.title){ await this.request(`/api/cards/${card.id}`,{method:"PATCH",body:JSON.stringify({title})}); await this.refresh(); this.message=`Renamed “${card.title}” to “${title}”`; } }); }}>
          <input name="title" aria-label="Card title" maxlength="120" required .value=${card.title} autofocus @keydown=${(event:KeyboardEvent) => { if (event.key === "Enter") (event.currentTarget as HTMLInputElement).form?.requestSubmit(); }}>
          <x-command-button @click=${() => this.openCardId = null}>CANCEL</x-command-button>
          <x-command-button @click=${(event:Event) => (event.currentTarget as Element).closest("form")?.requestSubmit()}>SAVE</x-command-button>
        </form>
        <h3 class="log-heading">ACTIVITY LOG</h3>
        ${notes.length ? html`<ol class="note-log">${notes.map(note => html`<li class="note">
          <time datetime=${new Date(note.created_at_ms).toISOString()}>${new Date(note.created_at_ms).toLocaleString()}</time>
          <p>${note.body}</p>
        </li>`)}</ol>` : html`<x-empty-state heading="NO NOTES"></x-empty-state>`}
        <form class="note-form" @submit=${(event:Event) => this.appendNote(event, card)}>
          <textarea name="note" aria-label="New note" maxlength="2000" required></textarea>
          <x-command-button @click=${(event:Event) => (event.currentTarget as Element).closest("form")?.requestSubmit()}>LOG</x-command-button>
        </form>
      </section>
    </div>`;
  }

  render() {
    return html`<x-console-shell>
      <x-utility-rail slot="header"><strong class="brand">KANBAN // 01</strong>
        <x-command-button title=${this.board?.undo_description ?? "Nothing to undo"} .disabled=${!this.board?.can_undo} @click=${() => void this.history("undo")}>UNDO</x-command-button>
        <x-command-button title=${this.board?.redo_description ?? "Nothing to redo"} .disabled=${!this.board?.can_redo} @click=${() => void this.history("redo")}>REDO</x-command-button>
        <span class="context">DELIVERY CONTROL</span><x-status-indicator class="push" label=${this.failed ? "ERROR" : "LOCAL"} tone=${this.failed ? "orange" : "green"}></x-status-indicator>
      </x-utility-rail>
      <section class="board" aria-label="Kanban board">${this.board?.columns.map((column,index) => this.renderColumn(column,index))}</section>
      <x-status-rail slot="footer" class=${this.failed ? "error" : ""}>${this.message}</x-status-rail>
    </x-console-shell>${this.renderModal()}`;
  }
}
customElements.define("x-kanban-board", KanbanBoard);

export function mount(root: HTMLElement): void {
  root.replaceChildren(document.createElement("x-kanban-board"));
}
