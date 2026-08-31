# Kanban Board — product specification

## User problem and outcome

A person needs one quick, trustworthy view of work moving through a process.
Kanban Board succeeds when that person can shape a single board, capture work,
prioritize it, and move it between stages without losing the chosen structure or
order after a process or browser restart. The product is deliberately local and
single-user: personal workflow clarity is the objective, not collaboration.

## Walking skeleton

The application opens one durable board with three initially seeded columns:
Backlog, In Progress, and Done. The user can rename, add, reorder, and delete
empty columns. At least one column must always remain, column names cannot be
blank, and deleting a column containing cards is rejected so work is never
silently discarded.

A card has a stable identity, title, optional plain-text description, column,
and position. The user can create a card, edit its title and description, move
it within or between columns by trusted mouse dragging, and delete it after
confirmation. Titles cannot be blank. Column and card order is explicit,
gap-free, deterministic, and updated atomically. Every mutation preserves UTC
creation and update timestamps.

SQLite is the default durable store at `data/kanban.db`;
`KANBAN_DATABASE_URL` may select another SQLAlchemy database. FastAPI owns the
authoritative state and serves one self-contained compiled Preact artifact. The
API exposes board retrieval plus explicit column and card mutation routes; it
rejects unknown identities, invalid targets, stale positions, and destructive
column deletion without partially changing the board.

## Real-world pilot and acceptance

Use the running application to model one actual workflow with at least four
cards. Rename the initial columns, add and reorder a fourth column, edit a card's
description, reorder two cards within one column, and drag cards across two
different column boundaries. Restart the service and browser and confirm the
column structure, card content, and exact ordering survive. Delete a card, then
delete its empty column, and confirm both disappear from the authoritative API.

Automated acceptance covers initial seeding, all column and card mutations,
validation failures, protected non-empty column deletion, deterministic order,
atomic cross-column movement, missing identities, restart persistence, strict
modular TypeScript compilation, self-contained FastAPI delivery, and wide and
narrow browser journeys. Mouse dragging proves the primary direct-manipulation
path; accessible edit controls provide the keyboard path.

## Deferred scope

Multiple boards, authentication, collaboration, assignees, labels, due dates,
attachments, comments, activity history, WIP limits, filtering, search,
archiving, and external synchronization are intentionally deferred. Kanban
policy and board rendering remain app-owned until another monoapp proves a
shared abstraction.
