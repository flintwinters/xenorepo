/** Month-first durable planning composed from central Preact UI primitives. */
import { Component, render } from "preact";
import { CommandButton, ConsolePane, ConsoleShell, EmptyState, StatusRail, UtilityRail } from "@xenorepo/ui";
import {
  createEvent,
  deleteEvent,
  initializeTimeZone,
  loadCalendar,
  updateEvent,
  type CalendarEvent,
  type CalendarView,
  type EventCreate,
} from "./client.js";
import "./styles.css";

const iso = (value: Date): string => value.toISOString().slice(0, 10);
const fromIso = (value: string): Date => new Date(`${value}T12:00:00Z`);
function addDays(value: Date, count: number): Date {
  const result = new Date(value);
  result.setUTCDate(result.getUTCDate() + count);
  return result;
}
function today(): string {
  const value = new Date(),
    month = String(value.getMonth() + 1).padStart(2, "0");
  return `${value.getFullYear()}-${month}-${String(value.getDate()).padStart(2, "0")}`;
}
function monthOf(value: string): Date {
  const date = fromIso(value);
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1, 12));
}
function cellsFor(anchor: Date): string[] {
  const first = addDays(anchor, -anchor.getUTCDay());
  return Array.from({ length: 42 }, (_, index) => iso(addDays(first, index)));
}
const shortTime = (value?: string | null): string => value?.slice(0, 5) ?? "";

interface State {
  view: CalendarView | null;
  selected: string;
  anchor: Date;
  editing: CalendarEvent | null;
  creating: boolean;
  message: string;
  failed: boolean;
  allDay: boolean;
}
interface Drag {
  item: CalendarEvent;
  element: HTMLElement;
  id: number;
  x: number;
  y: number;
  active: boolean;
}

class CalendarConsole extends Component<Record<string, never>, State> {
  override state: State = {
    view: null,
    selected: today(),
    anchor: monthOf(today()),
    editing: null,
    creating: false,
    message: "Loading month…",
    failed: false,
    allDay: false,
  };
  private drag: Drag | null = null;
  private suppressClick = false;

  override componentDidMount(): void {
    void this.perform(async () => {
      await this.refresh(true);
      this.setState({ message: "Calendar ready" });
    });
  }
  private perform = async (action: () => Promise<void>): Promise<void> => {
    try {
      await action();
      this.setState({ failed: false });
    } catch (error) {
      this.setState({ failed: true, message: error instanceof Error ? error.message : "Unexpected error" });
    }
  };
  private async refresh(initialize = false, anchor = this.state.anchor): Promise<void> {
    const cells = cellsFor(anchor),
      start = cells[0]!,
      end = iso(addDays(fromIso(cells[41]!), 1));
    const view = await loadCalendar(start, end);
    if (initialize && !view.time_zone) {
      const time_zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      await initializeTimeZone(time_zone);
      this.setState({ view: { ...view, time_zone } });
      return;
    }
    this.setState({ view });
  }
  private events(date: string): CalendarEvent[] {
    return this.state.view?.events.filter((item) => item.date === date) ?? [];
  }
  private navigate = (offset: number): void => {
    const anchor = new Date(
      Date.UTC(this.state.anchor.getUTCFullYear(), this.state.anchor.getUTCMonth() + offset, 1, 12),
    );
    this.setState({ anchor, selected: iso(anchor) }, () => void this.perform(() => this.refresh()));
  };
  private goToday = (): void => {
    const selected = today();
    this.setState({ selected, anchor: monthOf(selected) }, () => void this.perform(() => this.refresh()));
  };
  private openCreate = (date = this.state.selected): void =>
    this.setState({ selected: date, editing: null, creating: true, allDay: false });
  private openEdit = (item: CalendarEvent): void => {
    if (!this.suppressClick) this.setState({ editing: item, creating: false, allDay: item.all_day });
  };
  private closeEditor = (): void => this.setState({ editing: null, creating: false });
  private save = (event: SubmitEvent): void => {
    event.preventDefault();
    const data = new FormData(event.currentTarget as HTMLFormElement);
    const all_day = data.get("all_day") === "on";
    const payload: EventCreate = {
      title: String(data.get("title")),
      date: String(data.get("date")),
      all_day,
      start_time: all_day ? null : String(data.get("start_time")),
      end_time: all_day ? null : String(data.get("end_time")),
      location: String(data.get("location") || "") || null,
      notes: String(data.get("notes") || "") || null,
    };
    const existing = this.state.editing;
    void this.perform(async () => {
      if (existing) await updateEvent(existing.id, payload);
      else await createEvent(payload);
      const selected = payload.date;
      this.setState({ selected, anchor: monthOf(selected), editing: null, creating: false });
      await this.refresh(false, monthOf(selected));
      this.setState({ message: `${existing ? "Updated" : "Created"} “${payload.title.trim()}”` });
    });
  };
  private removeEvent = (item: CalendarEvent): void => {
    if (!window.confirm(`Delete “${item.title}”?`)) return;
    void this.perform(async () => {
      await deleteEvent(item.id);
      this.closeEditor();
      await this.refresh();
      this.setState({ message: `Deleted “${item.title}”` });
    });
  };
  private pointerStart = (event: PointerEvent, item: CalendarEvent): void => {
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
  };
  private pointerMove = (event: PointerEvent): void => {
    if (!this.drag || this.drag.id !== event.pointerId) return;
    if (!this.drag.active && Math.hypot(event.clientX - this.drag.x, event.clientY - this.drag.y) < 5) return;
    event.preventDefault();
    if (!this.drag.active) {
      this.drag.active = true;
      this.drag.element.classList.add("dragging");
    }
    document.querySelectorAll(".day.drop").forEach((value) => value.classList.remove("drop"));
    this.dropCell(event.clientX, event.clientY)?.classList.add("drop");
  };
  private pointerEnd = (event: PointerEvent): void => {
    const drag = this.drag;
    if (!drag || drag.id !== event.pointerId) return;
    const destination = drag.active ? this.dropCell(event.clientX, event.clientY)?.dataset.date : undefined;
    this.finishDrag();
    if (!destination || destination === drag.item.date) return;
    this.suppressClick = true;
    setTimeout(() => {
      this.suppressClick = false;
    }, 0);
    void this.perform(async () => {
      await updateEvent(drag.item.id, { date: destination });
      this.setState({ selected: destination });
      await this.refresh();
      this.setState({ message: `Moved “${drag.item.title}”` });
    });
  };
  private dropCell(x: number, y: number): HTMLElement | null {
    return document.elementFromPoint(x, y)?.closest<HTMLElement>(".day") ?? null;
  }
  private finishDrag = (): void => {
    this.drag?.element.classList.remove("dragging");
    this.drag = null;
    document.querySelectorAll(".day.drop").forEach((value) => value.classList.remove("drop"));
  };

  private day(date: string) {
    const items = this.events(date),
      outside = fromIso(date).getUTCMonth() !== this.state.anchor.getUTCMonth();
    const classes = [
      "day",
      outside && "outside",
      date === this.state.selected && "selected",
      date === today() && "today",
    ]
      .filter(Boolean)
      .join(" ");
    return (
      <div
        class={classes}
        role="button"
        tabIndex={0}
        data-date={date}
        aria-label={date}
        onClick={() => this.setState({ selected: date })}
        onKeyDown={(event) => {
          if (event.key === "Enter") this.setState({ selected: date });
        }}
        onDblClick={() => this.openCreate(date)}
      >
        <span class="number">{fromIso(date).getUTCDate()}</span>
        <span class="chips">
          {items.slice(0, 3).map((item) => (
            <button
              class={`chip ${item.all_day ? "all-day" : ""}`}
              aria-label={`${item.title}, ${item.all_day ? "all day" : shortTime(item.start_time)}`}
              onClick={(event) => {
                event.stopPropagation();
                this.openEdit(item);
              }}
              onPointerDown={(event) => this.pointerStart(event, item)}
              onPointerMove={this.pointerMove}
              onPointerUp={this.pointerEnd}
              onPointerCancel={this.finishDrag}
            >
              {item.all_day ? "" : shortTime(item.start_time)} {item.title}
            </button>
          ))}
          {items.length > 3 && <span class="more">+{items.length - 3}</span>}
        </span>
      </div>
    );
  }
  private editor() {
    if (!this.state.creating && !this.state.editing) return null;
    const item = this.state.editing;
    const values = item ?? {
      title: "",
      date: this.state.selected,
      start_time: "09:00",
      end_time: "10:00",
      location: "",
      notes: "",
    };
    return (
      <div
        class="backdrop"
        onClick={(event) => {
          if (event.target === event.currentTarget) this.closeEditor();
        }}
      >
        <section class="dialog" role="dialog" aria-modal="true" aria-labelledby="editor-title">
          <h2 id="editor-title">{item ? "EDIT EVENT" : "NEW EVENT"}</h2>
          <form onSubmit={this.save}>
            <label>
              Title
              <input name="title" required maxLength={200} value={values.title} />
            </label>
            <label>
              Date
              <input name="date" type="date" required value={values.date} />
            </label>
            <label class="all-day-field">
              <input
                name="all_day"
                type="checkbox"
                checked={this.state.allDay}
                onChange={(event) => this.setState({ allDay: event.currentTarget.checked })}
              />
              All day
            </label>
            <div class="times">
              <label>
                Start
                <input
                  name="start_time"
                  type="time"
                  required={!this.state.allDay}
                  disabled={this.state.allDay}
                  value={shortTime(values.start_time)}
                />
              </label>
              <label>
                End
                <input
                  name="end_time"
                  type="time"
                  required={!this.state.allDay}
                  disabled={this.state.allDay}
                  value={shortTime(values.end_time)}
                />
              </label>
            </div>
            <label>
              Location
              <input name="location" maxLength={2000} value={values.location ?? ""} />
            </label>
            <label>
              Notes
              <textarea name="notes" maxLength={2000} value={values.notes ?? ""} />
            </label>
            <div class="actions">
              {item && (
                <CommandButton class="delete-action" type="button" onClick={() => this.removeEvent(item)}>
                  DELETE
                </CommandButton>
              )}
              <CommandButton type="button" onClick={this.closeEditor}>
                CANCEL
              </CommandButton>
              <CommandButton type="submit">SAVE</CommandButton>
            </div>
          </form>
        </section>
      </div>
    );
  }
  private agendaRow(item: CalendarEvent) {
    return (
      <article
        class={`agenda-row ${item.all_day ? "all-day" : ""}`}
        tabIndex={0}
        onClick={() => this.openEdit(item)}
        onKeyDown={(event) => {
          if (event.key === "Enter") this.openEdit(item);
        }}
        onPointerDown={(event) => this.pointerStart(event, item)}
        onPointerMove={this.pointerMove}
        onPointerUp={this.pointerEnd}
        onPointerCancel={this.finishDrag}
      >
        <button class="drag-handle" aria-label={`Move ${item.title}`}>
          ⋮⋮
        </button>
        <span class="when">{item.all_day ? "ALL DAY" : shortTime(item.start_time)}</span>
        <span class="details">
          <strong>{item.title}</strong>
          {item.location && <span>{item.location}</span>}
        </span>
      </article>
    );
  }
  override render() {
    const { anchor, selected, failed, message, view } = this.state,
      cells = cellsFor(anchor),
      agenda = this.events(selected);
    const month = anchor.toLocaleDateString(undefined, { month: "long", year: "numeric", timeZone: "UTC" });
    const chosen = fromIso(selected).toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
      timeZone: "UTC",
    });
    const header = (
      <UtilityRail>
        <span class="brand">CALENDAR // 01</span>
        <span class="context">MONTH-FIRST PERSONAL PLANNER</span>
      </UtilityRail>
    );
    const footer = (
      <StatusRail>
        <span class={`status-indicator ${failed ? "orange" : "green"}`} role="status">
          {message}
        </span>
        <span class="push">{view?.time_zone ?? "LOCAL TIME"}</span>
      </StatusRail>
    );
    const controls = (
      <>
        <CommandButton aria-label="Previous month" onClick={() => this.navigate(-1)}>
          PREV
        </CommandButton>
        <CommandButton onClick={this.goToday}>TODAY</CommandButton>
        <CommandButton aria-label="Next month" onClick={() => this.navigate(1)}>
          NEXT
        </CommandButton>
      </>
    );
    return (
      <div class="calendar-console">
        <ConsoleShell class="calendar-shell" header={header} footer={footer}>
          <section class="workspace">
            <ConsolePane title={month} titleEnd={controls} tone="blue">
              <div class="month">
                <div class="weekdays">
                  {["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"].map((day) => (
                    <span>{day}</span>
                  ))}
                </div>
                <div class="grid">{cells.map((date) => this.day(date))}</div>
              </div>
            </ConsolePane>
            <ConsolePane title="AGENDA" tone="green">
              <div class="agenda">
                <div class="agenda-head">
                  <strong>{chosen}</strong>
                  <span class="push" />
                  <CommandButton onClick={() => this.openCreate()}>ADD</CommandButton>
                </div>
                <div class="agenda-list">
                  {agenda.length ? agenda.map((item) => this.agendaRow(item)) : <EmptyState heading="NO EVENTS" />}
                </div>
              </div>
            </ConsolePane>
          </section>
          {this.editor()}
        </ConsoleShell>
      </div>
    );
  }
}
export function mount(root: HTMLElement): void {
  render(<CalendarConsole />, root);
}
