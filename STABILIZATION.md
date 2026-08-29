# Monotools Stabilization Ledger

## Invariant

Monotools is the product and monoapps are independent proving grounds. The only
allowed dependency direction is:

```text
monoapp -> generic Monotools contract
Monotools -> no monoapp
```

Central source, tests, packages, tooling, and documentation must not statically
encode a monoapp identity, domain model, product policy, route, environment
variable, selector, or workflow. App identities may appear centrally only as
runtime values returned by metadata discovery. Central tests use synthetic
fixture apps with invented identities and domains. Shared custom elements
require at least two independent monoapp consumers. `historic/` remains
untracked, untouched, and outside validation.

Every monoapp also declares its cross-boundary production imports in `app.yaml`.
This makes its shared dependencies visible to an agent without source inference,
and validation rejects declarations that drift from the app-owned source.

## Violation inventory

`uv run manage.py audit` is the authoritative read-only inventory. It derives
app identities at runtime, excludes `historic/` and generated data, limits
source files to 600 physical lines, and computes cyclomatic complexity with a
maximum of 8 for Python, TypeScript, and JavaScript functions. Authored HTML is
an architecture violation; HTML exists only as generated `dist/` output.

The checkpoint 9 baseline is:

- Architecture: 0 violations across central identity isolation, cross-app
  imports, frontend package boundaries, and shared custom-element adoption.
- File size: 0 violations.
- Function complexity: 0 violations.

- Root tests now use invented fixture apps or runtime-discovered values; product
  assertions, production imports, and owned suite identities have been removed
  from the central suite and preserved beside their owning monoapps.
- Platform lifecycle and management code is generic: app managers own product
  runtime policy, and the legacy global CLI and compatibility views are gone.
- Shared-library exports and their independent consumer counts are inventoried
  in `LIBRARIES.md`; the shared UI surface contains only proved elements.
- Central and app-owned Python, TypeScript, and JavaScript are all within the
  recorded size, line-length, and complexity ceilings.
- Lifecycle, metadata, browser-validation, watching, and UI-runner internals
  are decomposed below the complexity ceiling with their observable contracts
  preserved.
- App-owned controllers, transactions, realtime handlers, and browser views are
  decomposed without crossing product boundaries or changing their contracts.
- Root `check` and `verify` permanently reject every recorded architecture,
  file-size, and function-complexity violation before app builds begin.
- Application HTML exists only as ignored compiled `dist/` output. Metadata
  accepts only JavaScript or TypeScript frontend entries, and architecture
  auditing rejects authored HTML anywhere in a monoapp.

## Checkpoint status

1. **Persist the corrected mission — complete.** Root policy and library
   documentation are generic, product roadmaps are app-owned, cross-boundary
   imports are visible and validated from app metadata, and the complete
   verification matrix passed on 2026-08-27.
2. **Evacuate monoapp behavior from root tests — complete.** Generic metadata,
   lifecycle, HTTP, realtime, ORM, browser, and evidence contracts use synthetic
   fixtures. Product persistence, migration, copy, composition, runtime policy,
   selectors, adapters, and suite assertions are app-owned. The complete
   verification matrix passed on 2026-08-27.
3. **Remove domain-aware platform code — complete.** The legacy global CLI,
   app-specific serving policy, manager compatibility wrapper, and single-page
   metadata views are removed. All callers use app-owned managers and generic
   `serve_app` parameters. The complete verification matrix passed on
   2026-08-27.
4. **Audit shared libraries — complete.** Shared Monotools, browser-testing,
   and Lit UI contract adoption is inventoried without centralizing app
   identities. Three zero-consumer custom elements and their types are removed,
   all Lit UI consumers use the package boundary, and the remaining elements
   each have at least two independent consumers. The complete verification
   matrix passed on 2026-08-28.
5. **Make structural debt measurable — complete.** Root `audit` reports stable
   architecture, file-size, and cross-language cyclomatic inventories without
   mutation. Root `check` and therefore `verify` reject architecture drift while
   reporting structural debt for the next two checkpoints. The initial
   architecture violation was removed, the inventory is locked by synthetic
   and repository-level tests, and the complete verification matrix passed on
   2026-08-28.
6. **Repair central builder internals — complete.** Manager discovery,
   metadata parsing, lifecycle validation, browser-proof validation, frontend
   watching, UI evidence orchestration, and shared browser-test analysis are
   decomposed to complexity 8 or lower. Architecture remains clean and the
   complete verification matrix passed on 2026-08-28.
7. **Repair monoapps independently — complete.** Every app-owned controller is
   decomposed to complexity 8 or lower, and every app-owned presentation module
   is below 600 physical lines. Persistence transaction boundaries, realtime
   and process protocols, browser behavior, and artifact contracts are
   preserved. The complete verification matrix passed on 2026-08-28.
8. **Activate permanent gates — complete.** Root `check` and therefore
   `verify` reject architecture, file-size, and function-complexity violations
   before building any monoapp. The read-only `audit` inventory remains
   available, synthetic management tests prove each violation category is a
   hard failure, and the complete verification matrix passed on 2026-08-28.
9. **Eliminate authored HTML — complete.** Every monoapp frontend is compiled
   from JavaScript or TypeScript through the Lit bundle pipeline. The legacy
   document parser and metadata format are removed, app metadata rejects HTML
   sources, architecture auditing rejects any app-owned HTML outside generated
   directories, and JavaScript is covered by the source line-length gate. The
   complete verification matrix passed on 2026-08-28.

## Preact migration

The active migration replaces all nine remaining Lit or imperative frontends
with strict Preact TSX and external CSS while preserving the self-contained
FastAPI artifact contract. HTTP types will be generated from app-owned OpenAPI
schemas; realtime protocols remain app-owned runtime-checked unions. The Lit
builder remains only until the last production consumer has migrated.

1. **Characterize the existing UI — complete.** Every monoapp owns deterministic
   wide and narrow visual baselines. Previously missing browser suites now
   characterize enrollment, account mode, and keyboard inventory behavior.
   Existing acceptance and trusted-input journeys remain unchanged.
2. **Add generic Preact and API tooling — complete.** Metadata accepts only TSX
   Preact entries, strict entry-rooted diagnostics precede `dist/` mutation,
   imported CSS and JavaScript are inlined, and API-only OpenAPI declarations
   are deterministically generated under ignored app data. Watchers, CSS
   structural gates, locked dependencies, and synthetic platform tests cover
   these contracts while Lit remains runnable.
3. **Prove shared Preact UI — in progress.** Introduce only components jointly
   proved by two independent consumers and migrate that first pair.
4. **Migrate the realtime and scheduling pair — pending.** Add the independently
   proved empty state and preserve realtime and trusted pointer behavior.
5. **Migrate the board — pending.** Preserve ordering, dialogs, history,
   pointer capture, notes, and durable review state.
6. **Migrate the cockpit — pending.** Preserve its complete journey and
   strengthen its OpenAPI response contracts.
7. **Migrate the event-stream consumer — pending.** Replace imperative DOM and
   unsafe HTML with typed JSX while preserving HTTP, authentication, and
   pagination.
8. **Migrate the inventory — pending.** Replace imperative rendering with typed
   state while preserving scoring, keyboard flow, completion, and restart.
9. **Migrate the realtime arena — pending.** Split typed state, view, and
   transport while preserving its complete protocol and behavior.
10. **Remove Lit compatibility — pending.** Remove Lit and JavaScript frontend
    support and activate permanent Preact architecture gates.

## Next action

Create the typed shared Preact package from the boundaries independently proved
by the first two consumers, migrate that pair with external CSS and generated
HTTP types, and preserve their verified visual baselines.
