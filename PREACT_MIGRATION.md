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

- [x] **Foundation — complete.** All apps own deterministic wide and narrow visual
  baselines. Monotools supports strict TSX entrypoints, external CSS inlining,
  entry-rooted diagnostics, generated OpenAPI declarations, and deterministic
  watching without mutating `dist/` after a failed diagnostic.
- [x] **Shared UI proof — complete.** Two independent consumers use the typed
  shared shell, pane, rail, and command boundaries. The stateful consumer
  preserves keyboard and persistence behavior; the HTTP consumer uses its
  generated client.
- [x] **Realtime and scheduling pair — complete.** Both consumers prove the shared
  typed empty-state boundary while preserving runtime-checked socket events,
  generated HTTP types, date calculations, and trusted pointer behavior.
- [x] **Board — complete.** Ordering, dialogs, history, trusted pointer capture,
  notes, and durable review state are preserved through generated HTTP types.
- [x] **Cockpit — complete.** Preserved the complete journey and strengthened its
  OpenAPI response contracts.
- [x] **Event-stream consumer — complete.** Typed JSX, generated HTTP contracts,
  authentication, pagination parameters, and lifecycle-owned SSE preserve the wire.
- [x] **Inventory — complete.** Typed Preact state preserves scoring, keyboard
  flow, completion, restart, and the non-diagnostic product boundary.
- [x] **Realtime arena — complete.** Split typed state, view, and transport while
  preserving the complete protocol and behavior.
- [x] **Compatibility removal — complete.** Lit builders, configuration, and
  dependencies are removed. Metadata accepts only Preact TSX entries, and the
  architecture audit rejects authored JavaScript in production frontend trees.

## Current checkpoint

The Preact migration is complete. Keep the Preact-only metadata and production
source gates permanent; address future frontend work as independent product or
shared-contract checkpoints.
