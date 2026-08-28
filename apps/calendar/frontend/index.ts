/** Month-first durable planning composed from central Lit UI primitives. */
import { LitElement, html, nothing } from "lit";
import { calendarStyles } from "./styles.js";

interface CalendarEvent {
  id: string;
  title: string;
  date: string;
  all_day: boolean;
  start_time: string | null;
  end_time: string | null;
  location: string | null;
  notes: string | null;
}
interface CalendarView {
  time_zone: string | null;
  events: CalendarEvent[];
}
const iso = (value: Date) => value.toISOString().slice(0, 10);
const fromIso = (value: string) => new Date(`${value}T12:00:00Z`);
const addDays = (value: Date, count: number) => {
  const result = new Date(value);
  result.setUTCDate(result.getUTCDate() + count);
  return result;
};
const today = () => {
  const value = new Date();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${value.getFullYear()}-${month}-${day}`;
};
const monthOf = (value: string) => {
  const date = fromIso(value);
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1, 12));
};
const cellsFor = (anchor: Date) => {
  const first = addDays(anchor, -anchor.getUTCDay());
  return Array.from({ length: 42 }, (_, i) => iso(addDays(first, i)));
};
const shortTime = (value: string | null) => value?.slice(0, 5) ?? "";

class CalendarConsole extends LitElement {
  static properties = {
    view: { state: true },
    selected: { state: true },
    anchor: { state: true },
    editing: { state: true },
    creating: { state: true },
    message: { state: true },
    failed: { state: true },
    allDay: { state: true },
  };
  declare view: CalendarView | null;
  declare selected: string;
  declare anchor: Date;
  declare editing: CalendarEvent | null;
  declare creating: boolean;
  declare message: string;
  declare failed: boolean;
  declare allDay: boolean;
  private drag: {
    item: CalendarEvent;
    element: HTMLElement;
    id: number;
    x: number;
    y: number;
    active: boolean;
  } | null = null;
  private suppressClick = false;
  constructor() {
    super();
    this.view = null;
    this.selected = today();
    this.anchor = monthOf(this.selected);
    this.editing = null;
    this.creating = false;
    this.message = "Loading month…";
    this.failed = false;
    this.allDay = false;
  }

  static styles = calendarStyles;

  connectedCallback() {
    super.connectedCallback();
    void this.perform(async () => {
      await this.refresh(true);
      this.message = "Calendar ready";
    });
  }
  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options?.headers },
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { error?: string; detail?: unknown } | null;
      throw new Error(
        body?.error ?? (typeof body?.detail === "string" ? body.detail : `Request failed (${response.status})`),
      );
    }
    return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
  }
  private async perform(action: () => Promise<void>) {
    try {
      await action();
      this.failed = false;
    } catch (error) {
      this.failed = true;
      this.message = error instanceof Error ? error.message : "Unexpected error";
    }
  }
  private range() {
    const cells = cellsFor(this.anchor);
    return { start: cells[0], end: iso(addDays(fromIso(cells[41]), 1)) };
  }
  private async refresh(initialize = false) {
    const range = this.range();
    this.view = await this.request<CalendarView>(`/api/calendar?start=${range.start}&end=${range.end}`);
    if (initialize && !this.view.time_zone) {
      const time_zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      await this.request("/api/settings/time-zone", { method: "PUT", body: JSON.stringify({ time_zone }) });
      this.view = { ...this.view, time_zone };
    }
  }
  private events(date: string) {
    return this.view?.events.filter((item) => item.date === date) ?? [];
  }
  private navigate(offset: number) {
    this.anchor = new Date(Date.UTC(this.anchor.getUTCFullYear(), this.anchor.getUTCMonth() + offset, 1, 12));
    this.selected = iso(this.anchor);
    void this.perform(() => this.refresh());
  }
  private goToday() {
    this.selected = today();
    this.anchor = monthOf(this.selected);
    void this.perform(() => this.refresh());
  }
  private openCreate(date = this.selected) {
    this.selected = date;
    this.editing = null;
    this.creating = true;
    this.allDay = false;
  }
  private openEdit(item: CalendarEvent) {
    if (this.suppressClick) return;
    this.editing = item;
    this.creating = false;
    this.allDay = item.all_day;
  }
  private closeEditor() {
    this.editing = null;
    this.creating = false;
  }
  private save(event: SubmitEvent) {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const data = new FormData(form);
    const all_day = data.get("all_day") === "on";
    const payload = {
      title: data.get("title"),
      date: data.get("date"),
      all_day,
      start_time: all_day ? null : data.get("start_time"),
      end_time: all_day ? null : data.get("end_time"),
      location: data.get("location") || null,
      notes: data.get("notes") || null,
    };
    const existing = this.editing;
    void this.perform(async () => {
      await this.request(existing ? `/api/events/${existing.id}` : "/api/events", {
        method: existing ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      this.selected = String(payload.date);
      this.anchor = monthOf(this.selected);
      this.closeEditor();
      await this.refresh();
      this.message = `${existing ? "Updated" : "Created"} “${String(payload.title).trim()}”`;
    });
  }
  private removeEvent(item: CalendarEvent) {
    if (!window.confirm(`Delete “${item.title}”?`)) return;
    void this.perform(async () => {
      await this.request(`/api/events/${item.id}`, { method: "DELETE" });
      this.closeEditor();
      await this.refresh();
      this.message = `Deleted “${item.title}”`;
    });
  }
  private pointerStart(event: PointerEvent, item: CalendarEvent) {
    const narrow = matchMedia("(max-width:720px)").matches;
    if (
      !event.isPrimary ||
      event.button !== 0 ||
      (narrow &&
        !event.composedPath().some((value) => value instanceof Element && value.classList.contains("drag-handle")))
    )
      return;
    const element = event.currentTarget as HTMLElement;
    this.drag = { item, element, id: event.pointerId, x: event.clientX, y: event.clientY, active: false };
    try {
      element.setPointerCapture(event.pointerId);
    } catch {
      /* synthetic pointer */
    }
  }
  private pointerMove(event: PointerEvent) {
    if (!this.drag || this.drag.id !== event.pointerId) return;
    if (!this.drag.active && Math.hypot(event.clientX - this.drag.x, event.clientY - this.drag.y) < 5) return;
    event.preventDefault();
    if (!this.drag.active) {
      this.drag.active = true;
      this.drag.element.classList.add("dragging");
    }
    this.renderRoot.querySelectorAll(".day.drop").forEach((value) => value.classList.remove("drop"));
    this.dropCell(event.clientX, event.clientY)?.classList.add("drop");
  }
  private pointerEnd(event: PointerEvent) {
    const drag = this.drag;
    if (!drag || drag.id !== event.pointerId) return;
    const destination = drag.active ? this.dropCell(event.clientX, event.clientY)?.dataset.date : undefined;
    this.finishDrag();
    if (!destination || destination === drag.item.date) return;
    this.suppressClick = true;
    setTimeout(() => (this.suppressClick = false), 0);
    void this.perform(async () => {
      await this.request(`/api/events/${drag.item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ date: destination }),
      });
      this.selected = destination;
      await this.refresh();
      this.message = `Moved “${drag.item.title}”`;
    });
  }
  private dropCell(x: number, y: number) {
    return (
      ((this.renderRoot as ShadowRoot).elementFromPoint(x, y) as Element | null)?.closest<HTMLElement>(".day") ?? null
    );
  }
  private finishDrag() {
    this.drag?.element.classList.remove("dragging");
    this.drag = null;
    this.renderRoot.querySelectorAll(".day.drop").forEach((value) => value.classList.remove("drop"));
  }

  private renderDay(date: string) {
    const items = this.events(date);
    const outside = fromIso(date).getUTCMonth() !== this.anchor.getUTCMonth();
    return html`<div
      class="day ${outside ? "outside" : ""} ${date === this.selected ? "selected" : ""} ${date === today()
        ? "today"
        : ""}"
      role="button"
      tabindex="0"
      data-date=${date}
      aria-label=${date}
      @click=${() => (this.selected = date)}
      @keydown=${(event: KeyboardEvent) => {
        if (event.key === "Enter") this.selected = date;
      }}
      @dblclick=${() => this.openCreate(date)}
    >
      <span class="number">${fromIso(date).getUTCDate()}</span
      ><span class="chips"
        >${items.slice(0, 3).map(
          (item) =>
            html`<button
              class="chip ${item.all_day ? "all-day" : ""}"
              aria-label=${`${item.title}, ${item.all_day ? "all day" : shortTime(item.start_time)}`}
              @click=${(event: Event) => {
                event.stopPropagation();
                this.openEdit(item);
              }}
              @pointerdown=${(event: PointerEvent) => this.pointerStart(event, item)}
              @pointermove=${this.pointerMove}
              @pointerup=${this.pointerEnd}
              @pointercancel=${this.finishDrag}
            >
              ${item.all_day ? "" : shortTime(item.start_time)} ${item.title}
            </button>`,
        )}${items.length > 3 ? html`<span class="more">+${items.length - 3}</span>` : nothing}</span
      >
    </div>`;
  }
  private renderEditor() {
    if (!this.creating && !this.editing) return nothing;
    const item = this.editing;
    const values = item ?? {
      title: "",
      date: this.selected,
      start_time: "09:00",
      end_time: "10:00",
      location: "",
      notes: "",
    };
    return html`<div
      class="backdrop"
      @click=${(event: Event) => {
        if (event.target === event.currentTarget) this.closeEditor();
      }}
    >
      <section class="dialog" role="dialog" aria-modal="true" aria-labelledby="editor-title">
        <h2 id="editor-title">${this.editorTitle()}</h2>
        <form @submit=${this.save}>
          <label>Title<input name="title" required maxlength="200" .value=${values.title} /></label
          ><label>Date<input name="date" type="date" required .value=${values.date} /></label
          ><label class="all-day-field"
            ><input
              name="all_day"
              type="checkbox"
              .checked=${this.allDay}
              @change=${(event: Event) => (this.allDay = (event.target as HTMLInputElement).checked)}
            />All day</label
          >
          <div class="times">
            <label
              >Start<input
                name="start_time"
                type="time"
                ?required=${!this.allDay}
                ?disabled=${this.allDay}
                .value=${shortTime(values.start_time)} /></label
            ><label
              >End<input
                name="end_time"
                type="time"
                ?required=${!this.allDay}
                ?disabled=${this.allDay}
                .value=${shortTime(values.end_time)}
            /></label>
          </div>
          <label>Location<input name="location" maxlength="2000" .value=${values.location} /></label
          ><label>Notes<textarea name="notes" maxlength="2000" .value=${values.notes}></textarea></label>
          <div class="actions">
            ${this.renderDeleteAction(item)}<x-command-button @click=${this.closeEditor}>CANCEL</x-command-button
            ><x-command-button @click=${() => this.renderRoot.querySelector("form")?.requestSubmit()}
              >SAVE</x-command-button
            >
          </div>
        </form>
      </section>
    </div>`;
  }
  private editorTitle() {
    return this.editing ? "EDIT EVENT" : "NEW EVENT";
  }
  private renderDeleteAction(item: CalendarEvent | null) {
    if (!item) return nothing;
    return html`<x-command-button class="delete-action" @click=${() => this.removeEvent(item)}
      >DELETE</x-command-button
    >`;
  }
  render() {
    const cells = cellsFor(this.anchor),
      agenda = this.events(this.selected);
    const month = this.anchor.toLocaleDateString(undefined, { month: "long", year: "numeric", timeZone: "UTC" });
    const chosen = fromIso(this.selected).toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
      timeZone: "UTC",
    });
    return html`<x-console-shell
      ><x-utility-rail slot="header"
        ><span class="brand">CALENDAR // 01</span
        ><span class="context">MONTH-FIRST PERSONAL PLANNER</span></x-utility-rail
      >
      <section class="workspace">
        <x-console-pane title=${month} index="01" tone="blue"
          ><x-command-button slot="title-end" @click=${() => this.navigate(-1)} label="Previous month"
            >PREV</x-command-button
          ><x-command-button slot="title-end" @click=${this.goToday}>TODAY</x-command-button
          ><x-command-button slot="title-end" @click=${() => this.navigate(1)} label="Next month"
            >NEXT</x-command-button
          >
          <div class="month">
            <div class="weekdays">
              ${["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"].map((day) => html`<span>${day}</span>`)}
            </div>
            <div class="grid">${cells.map((date) => this.renderDay(date))}</div>
          </div></x-console-pane
        ><x-console-pane title="AGENDA" index="02" tone="green"
          ><div class="agenda">
            <div class="agenda-head">
              <strong>${chosen}</strong><span class="push"></span
              ><x-command-button @click=${() => this.openCreate()}>ADD</x-command-button>
            </div>
            <div class="agenda-list">
              ${agenda.length
                ? agenda.map(
                    (item) =>
                      html`<article
                        class="agenda-row ${item.all_day ? "all-day" : ""}"
                        tabindex="0"
                        @click=${() => this.openEdit(item)}
                        @keydown=${(event: KeyboardEvent) => {
                          if (event.key === "Enter") this.openEdit(item);
                        }}
                        @pointerdown=${(event: PointerEvent) => this.pointerStart(event, item)}
                        @pointermove=${this.pointerMove}
                        @pointerup=${this.pointerEnd}
                        @pointercancel=${this.finishDrag}
                      >
                        <button class="drag-handle" aria-label=${`Move ${item.title}`}>⋮⋮</button
                        ><span class="when">${item.all_day ? "ALL DAY" : shortTime(item.start_time)}</span
                        ><span class="details"
                          ><strong>${item.title}</strong>${item.location
                            ? html`<span>${item.location}</span>`
                            : nothing}</span
                        >
                      </article>`,
                  )
                : html`<x-empty-state heading="NO EVENTS" detail=""></x-empty-state>`}
            </div>
          </div></x-console-pane
        >
      </section>
      <x-status-rail slot="footer"
        ><x-status-indicator tone=${this.failed ? "orange" : "green"} label=${this.message}></x-status-indicator
        ><span class="push">${this.view?.time_zone ?? "LOCAL TIME"}</span></x-status-rail
      >${this.renderEditor()}</x-console-shell
    >`;
  }
}
customElements.define("calendar-console", CalendarConsole);
export function mount(root: HTMLElement): void {
  root.append(document.createElement("calendar-console"));
}
