# Internal application platform

`monotools` is the repository's internal platform for independently deployable
FastAPI applications. It is intentionally not a public SDK: abstractions enter
only after more than one app has proved their boundary.

## App contract

Each app declares its name, title, importable FastAPI module, capabilities, and
frontend artifacts in `app.yaml`. Artifact source, output, and format are
independent facts; routes map server-owned URL paths to logical artifact names.
`python manage.py check` discovers every definition, validates its source
contract, imports its service, builds its browser documents, and validates the
resulting `dist/` directory. The service owns `/health`, its declared document
routes, and its domain routes.

Apps remain product owners. Domain entities, repositories, migrations,
authentication semantics, and high-level realtime coordinators stay local.

## Persistence

Application repositories expose domain operations instead of SQL details.
They receive a session factory built from their own SQLAlchemy metadata and
perform repeatable migrations before use. SQLite data belongs in the visible
per-app `data/` directory; schema evolution preserves existing facts and uses
typed relationships, constraints, and indexes rather than serialized state.

## HTTP and sessions

Browser state-changing HTTP requests accept a missing `Origin` for non-browser
clients, or require an origin whose scheme and authority match the request.
Capture client host, user agent, and origin as provenance when a domain session
is created. Platform JSON failures use `{"error": "..."}`. Session cookies are
HTTP-only, `SameSite=Lax`, path-scoped to `/`, and `Secure` only for HTTPS.
Cookie names and response schemas are app contracts and must not change during
platform migration.

## Realtime delivery

WebSocket handlers enforce same-origin browser connections and keep their
protocol and coordinators app-owned. Shared registries snapshot selected
connections before awaiting sends and report stale sockets for domain cleanup.
Streaming feeds may wait and construct an event while holding their
synchronization boundary, but must release every thread-owned lock before
yielding an event. Tests must include cross-thread publish/wait delivery.

## Frontend composition

Legacy document artifacts compose their semantic body, CSS, and script with the
shared console shell at build time. Lit artifacts export `mount(root)` and are
bundled centrally with esbuild; they import reusable elements only from
`@xenorepo/lit-ui`. Every artifact is self-contained: embedded CSS and
JavaScript, no external assets, and no separate frontend service. Use
modular TypeScript freely beneath an app's `frontend/` directory: Monotools
strictly validates the complete import graph rooted at each declared Lit entry
before mutating `dist/`, and watch mode recursively observes both that app tree
and the shared Lit UI sources. Imported modules require no metadata. Use
`python manage.py bootstrap` to verify Node 22, synchronize locked Python
dependencies, run `npm ci`, and install the locked Chromium browser before
frontend work.

## Required verification

All recurring checks run through `manage.py`. Every app manager exports a typed
`ApplicationManager` whose Python suite and optional browser suite live beneath
that app's `tests/` directory. `python manage.py test` runs the platform suite,
every app suite exactly once, and Monotools' trusted-input browser canaries.
`python manage.py verify` composes repository checks, all tests, and the complete
browser inventory.

## Browser verification

`python manage.py ui-check [app]` checks one app or all apps in deterministic
order. Every metadata-declared frontend route receives Monotools' universal
wide/narrow Chromium journey. Domain scenarios remain in
`apps/<app>/tests/e2e/` and use exactly one proof tag: `acceptance`,
`browser-integration`, `visual`, or `accessibility`. Viewport names never imply
input modality; trusted mouse, native Chromium touch, and keyboard evidence are
separate claims. Synthetic events may support browser-integration tests but
cannot satisfy trusted-input acceptance.

Static TypeScript parsing and Playwright enumeration run before builds or other
browser-lifecycle mutation. Each run retains `summary.json`, `playwright.log`,
`service.log`, the isolated browser database where applicable, and failure
screenshots/traces under `apps/<app>/data/ui-check/`. Pass `--evidence` to retain
trace, video, and HAR output for successful runs. Chromium automation is a
browser-input claim, not evidence about Safari or physical mobile hardware.
