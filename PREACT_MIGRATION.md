# Preact Migration

## Objective

Replace every production frontend with strict Preact TSX and external CSS,
preserving behavior and app-owned wide and narrow visual baselines. Remove Lit
and JavaScript frontend compatibility only after the final consumer migrates.

## Invariants

- FastAPI continues to serve one self-contained compiled `dist/` artifact.
- HTTP types come from app-owned OpenAPI schemas. Realtime protocols remain
  app-owned runtime-checked unions.
- Shared UI contains only typed boundaries proved by at least two independent
  monoapps; application behavior, copy, layout, and selectors remain app-owned.
- Root `check` and `verify` reject architecture violations, authored HTML,
  source files over 600 lines, and functions with complexity above 8.
- The dependency direction remains `monoapp -> generic Monotools contract`.

## Progress

- **Foundation — complete.** All apps own deterministic wide and narrow visual
  baselines. Monotools supports strict TSX entrypoints, external CSS inlining,
  entry-rooted diagnostics, generated OpenAPI declarations, and deterministic
  watching without mutating `dist/` after a failed diagnostic.
- **Shared UI proof — complete.** Two independent consumers use the typed
  shared shell, pane, rail, and command boundaries. The stateful consumer
  preserves keyboard and persistence behavior; the HTTP consumer uses its
  generated client.
- **Realtime and scheduling pair — active.** Add a shared empty-state boundary
  only after both consumers prove it. Preserve runtime-checked socket events,
  generated HTTP types, date calculations, and trusted pointer behavior.
- **Board — next.** Preserve ordering, dialogs, history, pointer capture, notes,
  and durable review state.
- **Cockpit — queued.** Preserve the complete journey and strengthen its
  OpenAPI response contracts.
- **Event-stream consumer — queued.** Replace imperative DOM and unsafe HTML
  with typed JSX while preserving HTTP, authentication, and pagination.
- **Inventory — queued.** Replace imperative rendering with typed state while
  preserving scoring, keyboard flow, completion, and restart.
- **Realtime arena — queued.** Split typed state, view, and transport while
  preserving the complete protocol and behavior.
- **Compatibility removal — queued.** Remove Lit and JavaScript frontend
  support and activate permanent Preact-only architecture gates.

## Current checkpoint

Complete the realtime and scheduling pair as one verified logical checkpoint.
Run `uv run manage.py verify`, update this file and `LIBRARIES.md` with the
proved shared boundary, and commit before beginning the board.
