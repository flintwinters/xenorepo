# Calendar Console — Product Specification

## User problem and product intent

A person needs one fast, trustworthy place to see a month and manage the commitments on a selected day. The product succeeds when planning a real month is quicker than using paper while dates, times, and details survive process and browser restarts exactly. Calendar is deliberately local and single-user: durable personal planning is the objective, not collaboration or calendar-provider compatibility.

## Feature inventory

- A Sunday-first month grid with previous-month, Today, and next-month navigation.
- A selected-day agenda beside the grid on wide screens and below it on narrow screens.
- Durable creation, precise editing, confirmed deletion, and date rescheduling for single-day events.
- All-day events and timed events with title, local date, start and end time, location, and notes.
- Mouse dragging between visible month cells and touch-oriented dragging from narrow agenda handles; the editor is the keyboard-accessible rescheduling path.
- One persisted IANA timezone, initialized from the first browser and never silently changed.
- Stable UUID identities, UTC audit timestamps, deterministic ordering, explicit validation, and visible API failures.

## Walking skeleton

The first shippable slice opens the current month, initializes the browser timezone once, and retrieves the visible date interval from FastAPI. Selecting a date shows its agenda. A user can create a timed or all-day event, edit every stored field, move it to another visible date, reload, and delete it. SQLite is the default durable store at `data/calendar.db`; `CALENDAR_DATABASE_URL` can select another SQLAlchemy database.

The service exposes:

- `GET /api/calendar?start=YYYY-MM-DD&end=YYYY-MM-DD` for the persisted timezone and events in an inclusive/exclusive interval.
- `PUT /api/settings/time-zone` for create-once, same-value-idempotent timezone initialization and conflict on change.
- `POST /api/events`, `PATCH /api/events/{id}`, and `DELETE /api/events/{id}` for validated atomic event mutation.

All-day events have null times. Timed events have both times and an increasing same-day interval. Titles cannot be blank. Dates and IANA zones must be real. Events sort by date, all-day first, start time, title, then stable ID.

## Real-world pilot and acceptance

Use the running application to plan at least five actual commitments in one month, including one all-day commitment and timed commitments with details. Reschedule one commitment by dragging, edit another precisely, restart both service and browser, and confirm that the month and selected-day agenda preserve the intended dates, ordering, times, location, and notes. Confirm deletion removes the event from both UI and authoritative API state.

Automated acceptance covers timezone initialization and conflict, same-origin enforcement, all CRUD paths, invalid intervals, deterministic range ordering, drag-equivalent date updates, missing identities, restart persistence, strict modular TypeScript compilation, self-contained FastAPI delivery, and wide/narrow browser journeys with trusted mouse/touch evidence.

## Deferred scope

Recurrence, reminders, multiple calendars, authentication, sharing, attendees, external synchronization or import, multi-day events, timezone changes, and server-side timezone conversion are intentionally deferred. Calendar-specific rendering and date arithmetic remain app-owned until another app proves a shared abstraction.
