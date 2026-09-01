# Kanban — Product Specification

## User problem and product intent

A person needs one calm, durable board for turning an unordered workload into visible progress.
The product succeeds when that person can shape a workflow around real work, move cards quickly,
and recover anything removed by mistake. Kanban is deliberately local and single-user: it has one
board, no accounts, no due dates, and no collaboration behavior.

## Feature inventory

- One persistent board whose name and description can be edited.
- User-created, named columns with explicit ordering and reversible archiving.
- Per-column Add Card controls in column headers.
- Cards with editable title, description, assignee text, labels, and priority.
- Board settings for its identity and default card priority, plus individual column, card, and
  label colors. The single board uses the shared application chrome rather than a custom theme.
- Mouse drag-and-drop for ordering cards within a column and moving them between columns.
- Editable comments, local file uploads, and web-link attachments.
- Reversible archiving for the board's columns, cards, comments, and attachments.
- An immutable activity history that records creation, edits, moves, archive, and restore actions.
- Stable UUID identities, UTC audit timestamps, deterministic ordering, explicit validation, and
  visible API failures.

## Walking skeleton

The first shippable slice opens the one board and presents its active columns and cards. A user can
rename the board, create and reorder columns, create a fully described card, drag it within and
between columns, add and edit comments, attach both a local file and a web link, and inspect the
resulting immutable history. An archive view restores any archived column, card, comment, or
attachment. SQLite is the default durable store at `data/kanban.db`;
`KANBAN_DATABASE_URL` can select another SQLAlchemy database.

The FastAPI service owns board state, multipart uploads, attachment delivery, validation, and
atomic mutations. Local uploads live under `data/uploads/` with generated storage names; original
names and media types remain domain metadata. Archiving an upload preserves its file for restore.
Active card positions are dense, zero-based integers within their column, and active column
positions follow the same invariant. A move transaction closes gaps and inserts the moved item at
the requested position. Labels are trimmed, nonblank, unique ignoring case, and retain their first
entered spelling. Priority is one of `low`, `normal`, `high`, or `urgent`.

Every successful mutation appends an activity record in the same transaction. Activity records
store their stable identity, event kind, subject identity and type, UTC occurrence time, and a
concise factual summary. They cannot be edited or archived. Restoring a child whose parent remains
archived is rejected, and a column can only be archived when all of its cards are already archived.

## Real-world pilot and acceptance

Use the running application to manage at least eight real tasks across at least three custom
columns. Populate priorities, labels, assignee text, comments, one web link, and one local upload.
Reorder two tasks, move tasks through the workflow by dragging, edit stored content, archive and
restore each recoverable entity type, restart both service and browser, and confirm the board,
ordering, uploaded file, archive state, and immutable activity history remain exact.

Automated acceptance covers initial board creation, all edit paths, column and card ordering,
cross-column moves, archive preconditions and restoration, comment and attachment lifecycles,
upload containment, link validation, activity immutability, invalid and missing identities,
same-origin mutation enforcement, restart persistence, strict modular TypeScript compilation,
self-contained FastAPI delivery, and populated wide/narrow browser journeys with real drag input.

## Deferred scope

Authentication, multiple boards, multiple users, live synchronization, due dates, reminders,
swimlanes, checklists, dependency graphs, search, saved filters, bulk operations, and external
storage providers are intentionally deferred. Card content is plain text. Kanban-specific board
policy and rendering remain app-owned until another app proves a shared abstraction.
