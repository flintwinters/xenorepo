# Preact Migration Regression Fixes

## Objective

Close the migration gaps found after fast-forwarding `main` from `6b23da7` to
`4b97d0b`. Preserve the completed Preact conversions and visual behavior while
restoring form semantics, meaningful parity evidence, runtime boundary checks,
proved shared abstractions, and the required stabilization record.

## Findings and acceptance criteria

### 1. Native command-button form semantics — high

`CommandButton` renders a native `<button>` without a default `type`. The
realtime messaging consumer places its send button inside a form and also calls
`requestSubmit()`, creating both a manual and an implicit submission path.

- Default the shared command button to `type="button"`.
- Keep explicit `type="submit"` only at intentional form submission sites.
- Remove redundant manual submission behavior where native form semantics are
  sufficient.
- Add browser coverage proving one click and one Enter action each produce
  exactly one durable message.

Evidence is owned by the shared UI package and the realtime messaging consumer's
frontend and browser suite.

### 2. Weakened visual parity thresholds — medium

The migration increased the realtime messaging consumer's allowed screenshot
difference from 300 to 5,500 pixels and the board consumer's from 300 to 1,500
pixels without changing their baseline images or recording a bounded source of
nondeterminism. These tolerances can hide layout and styling regressions.

- Measure the remaining raster differences in both wide and narrow viewports.
- Eliminate deterministic rendering differences when parity is achievable.
- Mask only genuinely dynamic regions, with each mask narrowly scoped.
- Restore a tight tolerance justified by measured platform variance.
- Record any intentional visual difference explicitly before accepting a new
  baseline.

Evidence is owned by the affected consumers' browser suites.

### 3. Unsafe HTTP error-envelope assertions — medium

The scheduling, board, and cockpit consumers cast `unknown` OpenAPI errors
directly to an assumed envelope. A primitive, array, or unexpected object
therefore enters the error path without runtime validation, and the same policy
is duplicated across three clients.

- Keep response errors typed as `unknown` until validated.
- Introduce an explicit structural predicate for the supported error envelope.
- Reuse one generic boundary only if all consumers truly share the same server
  contract; otherwise retain small app-owned guards.
- Cover primitive, array, expected-envelope, string-detail, and unexpected-object
  payloads through maintained tests.

Evidence is owned by the affected consumers' generated-client adapters.

### 4. Missing realtime parser coverage — medium

The realtime messaging consumer validates untrusted WebSocket payloads in
`parseServerEvent`, but its owned tests do not exercise the parser. Protocol
drift and malformed payload handling can therefore regress while the repository
gate remains green.

- Test every server-event discriminant: `history`, `message`, `presence`, and
  `error`.
- Test malformed top-level values, unknown discriminants, invalid nested
  messages, invalid counts, and missing required fields.
- Prove invalid payloads never enter typed product state and produce the intended
  visible transport error.

Evidence is owned by the realtime messaging consumer's type, transport, and test
modules.

### 5. Required stabilization ledger removed — medium

Commit `a1c84ca` deleted `STABILIZATION.md` and redirected repository context to
`PREACT_MIGRATION.md`. The current repository instructions require
`STABILIZATION.md` to retain the active checkpoint, violation inventory, and next
action so work remains resumable after context clearing.

- Restore a concise `STABILIZATION.md`.
- Keep the authoritative violation inventory, active checkpoint, and immediate
  next action there.
- Avoid duplicating the detailed migration roadmap: link to
  `PREACT_MIGRATION.md` for ordered migration work.
- Update root context consistently without discarding relevant historical
  invariants.

Evidence:

- commit `a1c84ca`
- `AGENTS.md`
- `PREACT_MIGRATION.md`

### 6. Duplicated status-indicator boundary — low

The realtime messaging and board consumers now independently implement
substantially equivalent `StatusIndicator` components. Two independent
consumers prove the shared UI boundary, but `@xenorepo/ui` does not expose it.

- Define a typed `StatusIndicator` in `packages/ui` using native HTML attribute
  props and stable shared classes.
- Preserve app-owned tone policy, labels, placement, and layout.
- Replace both local implementations without expanding the shared component into
  product behavior.
- Update `LIBRARIES.md` adoption counts and shared-component tests.

Evidence is owned by both consumer frontends, the shared UI package, and
`LIBRARIES.md`.

## Verification boundary

Address findings in small logical checkpoints. After each checkpoint, update
`STABILIZATION.md`, run `uv run manage.py verify`, and create a detailed commit
that records the preserved invariants and verification evidence. Completion
requires tight wide/narrow visual proofs, explicit HTTP and realtime malformed
payload coverage, exactly-once realtime-message submission behavior, a single
proved shared status indicator, and a clean nine-app structural audit.
