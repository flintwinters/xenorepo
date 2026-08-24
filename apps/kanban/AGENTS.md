# Project direction

## Motivation

This project is a compact, dependable kanban console. Favor an operable end-to-end workflow over breadth: every feature should preserve a clear path from the browser, through the API, to the board's authoritative state.

## Architecture

- FastAPI owns board HTTP behavior. A SQLAlchemy repository durably stores the
  single MVP board in SQLite by default while retaining backend portability.
- Every create, rename, reorder, move, and delete transaction records complete before/after card state plus a human-readable operation description. Undo and redo move a cursor through that history; a new mutation after undo discards the abandoned redo branch.
- Card positions are column-local, contiguous integers. SQLite snapshots and every history transition preserve their visible order; omitted move indexes append within the destination column.
- A Lit application in `frontend/` owns board-specific browser interactions and
  composes its shell, rails, panes, commands, status, and empty states from the
  central Lit UI package. Monotools compiles it into the self-contained
  `dist/index.html` served by FastAPI.
- Mutating HTTP routes use Monotools same-origin enforcement and its canonical
  domain-error envelope; the app owns only its error kinds and status mapping.
- Xenorepo's root `manage.py` is the one entrypoint for bootstrap, build, tests,
  and local serving; the app manager only declares its owned suites.
- Playwright validates the visible vertical slice against an isolated database
  under `data/ui-check/`; browser tests live in `tests/e2e/` and run through
  `python manage.py kanban ui-check`.

## Current big tasks

- The walking skeleton is established: one durable board supports creating, renaming, precisely ordering, moving, deleting, undoing, and redoing across the API boundary, with a reproducibly compiled client.
- The next meaningful product boundary is explicit board identity; do not add peripheral card metadata before multi-board ownership is designed.
