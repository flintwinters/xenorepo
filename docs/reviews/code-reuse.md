# Code reuse review

Source review, 2026-09-08. Recommendations only; no runtime changes. The existing
calendar submodule has local changes; its references describe the working tree.
`LIBRARIES.md` remains authoritative for adopted contracts and extraction policy.

## Prioritized opportunities

### 1. Share frontend HTTP outcome handling

Evidence: `result` in `apps/calendar/frontend/client.ts:10`,
`apps/kanban/frontend/client.ts:13`, and `apps/xenoview/frontend/client.ts:13`
is identical. `value` in `apps/microblog/frontend/client.ts:11` implements the
same logic with different fallback copy. These helpers cast unknown errors to
an envelope and distinguish missing data from successful values. Mailing list's
`errorMessage` (`apps/mailing_list/frontend/client.ts:23`) already checks runtime
types and understands validation arrays; MonoForm's `failureOutcome`
(`packages/monoui/src/monoform.tsx:188`) adds field-level presentation.

Proposal: extract a narrow, typed frontend transport contract under `packages/`
for decoding unknown error envelopes and requiring response data. Keep generated
OpenAPI clients, API paths, field mapping, and product copy with their owners.
Keep successful bodyless operations explicit instead of passing `undefined` to a
data-required helper. Reuse the established `openapi-fetch` integration rather
than creating another HTTP client. Register the contract before adoption.

Benefit: one place to fix malformed envelopes and validation-message handling
across at least four independent clients. Start with the three exact copies;
extend to other consumers only where their error precedence is compatible.
Weakest assumption: consumers want the same error interpretation. Reject or
narrow the extraction if it needs app identities or workflow-specific branches.
Verify false/zero/null data, absent data, bodyless success, malformed envelopes,
validation arrays, and network failures through root-managed contract tests and
the affected app journeys. Do not silently alter MonoForm's field errors.

### 2. Reuse the existing Preact bundler for MonoForm artifacts

Evidence: `monotools/node/build-preact.mjs:9` and
`monotools/node/build-monoform.mjs:8` duplicate the mount bootstrap, esbuild
configuration, JS/CSS output selection, directory creation, and writes.
`buildPageEntry` is already exported. MonoForm's meaningful differences are
manifest allowlisting and the compile-time `MONOFORM_MANIFEST` definition.

Proposal: extend the existing bundling function with a narrow compile-time
definitions option and let MonoForm call it after selecting its manifest.
Keep manifest validation and operation selection in the MonoForm wrapper.
Avoid a general build framework or freely overridable compiler policy.

Benefit: target, JSX, minification, CSS handling, and self-contained output
remain one platform decision. Weakest assumption: both artifact formats should
retain identical bundling policy; split only a demonstrated independent concern.
Use existing tooling tests, especially
`tests/test_tooling.py:169`, to preserve allowlisting and atomic final artifacts;
cover Preact output and absent CSS through the root test routine.

### 3. Centralize the repeated ASGI test client

Evidence: `Client` in `apps/calendar/tests/test_app.py:16`,
`apps/kanban/tests/test_app.py:18`, and `apps/xenoview/tests/test_app.py:20`
differs only in its base URL. Each wraps an HTTPX ASGI transport in a fresh async
client and uses `asyncio.run` to expose a synchronous request method.

Proposal: supply one generic, typed test-support adapter with explicit application
and base URL inputs through Monotools. `tests/support.py` already provides central
async test helpers, but monoapps should not acquire a dependency on Xenorepo's
private test suite, especially after submodule promotion. Evaluate existing
FastAPI/HTTPX facilities first; preserve current behavior if adopting a standard
client would change lifecycle or cookie semantics.

Benefit: fixes to transport cleanup and exception handling reach all three suites.
Weakest assumption: request-scoped clients are intentional. Specify cookie and
ASGI lifespan behavior before adoption; keep persistent-session clients distinct
if needed. Characterize request forwarding, raised application errors, and cleanup
in the root-managed platform suite, retaining domain assertions in each app.
Do not combine the apps' different database, upload, and restart fixtures into
an inheritance hierarchy merely because their setup methods look similar.

### 4. Adopt existing form primitives in bespoke workflows

Evidence: raw forms and controls appear in
`apps/mailing_list/frontend/index.tsx:164`,
`apps/microblog/frontend/index.tsx:204` and `:310`, and
`apps/chat/frontend/room.tsx:207`. The catalog already establishes `Form`,
`FormField`, `FormInput`, and `FormTextarea` in
`packages/monoui/src/form-controls.tsx` as native-attribute-compatible controls.

Proposal: incrementally replace matching structural controls with these existing
components. Keep checkout, authentication, publishing, and chat submission logic
app-owned. This is component adoption, not a reason to convert these workflows
to MonoForm or introduce a shared submission state machine.

Benefit: shared markup and control treatment evolve together without new public
abstractions. Weakest assumption: shared field geometry fits each design. Retain
local structures where adapting them would require workflow flags in MonoUI.
Verify labels, focus, keyboard submission, disabled states, and app-owned wide
and narrow visuals through root-managed browser checks.

### 5. Centralize root command app selection

Evidence: `ui_check`, `ui_hygiene`, and `aesthetic_check` in `manage.py` repeat
optional-name filtering against `MANAGERS` and the same unknown-app diagnostic.
The first and third return manager pairs; hygiene needs only each definition.

Proposal: add one root-local selection helper returning definition/manager pairs;
hygiene can ignore the manager. Keep this in repository composition rather than
making Monotools own Xenorepo's inventory. Existing environment activation and
command execution responsibilities need no new abstraction for this change.

Benefit: all-app selection and unknown-name behavior have one implementation.
Weakest assumption: these commands intentionally share selection semantics.
Keep distinct selectors if future commands admit planned or uninitialized apps.
Use the root-managed CLI tests for all apps, one known app, unknown names, and an
empty inventory; preserve diagnostics and exit status.

## Execution boundary

Start with bundling and CLI selection for small, reversible changes, then HTTP
outcomes and test support. Adopt form primitives per app with visual evidence.
For each extraction, retain product tests and introduce central tests only for
the shared contract; finish implementation checkpoints with
`uv run manage.py verify`. Revert an extraction if supporting its consumers
requires app policy inside the shared layer.

Keep domain stores, complete ORM tables, realtime protocols, routes, and workflow
state local. Existing database factories, HTTP server helpers, realtime primitives,
MonoUI, and MonoForm already cover substantial reuse; similar names or syntax
alone do not justify another abstraction.
