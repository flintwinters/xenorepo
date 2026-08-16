# Internal application platform

`tooling` is the repository's internal platform for independently deployable
FastAPI applications. It is intentionally not a public SDK: abstractions enter
only after more than one app has proved their boundary.

## App contract

Each app declares its name, title, importable FastAPI module, capabilities, and
frontend build inputs in `app.toml`. `python manage.py check` discovers every
definition, validates its source contract, imports its service, builds its
browser document, and validates the resulting `dist/` directory. The service
owns `/`, `/health`, and its domain routes; `/` always serves the app's
self-contained `dist/index.html`.

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

The platform composes each app's semantic body, app-specific CSS, and script
with the shared console shell at build time. The result is exactly one standalone
`dist/index.html`: embedded CSS and JavaScript, no external assets, and no
separate frontend service. Shared tokens and structural chrome belong in the
composition layer; product-specific semantics and behavior remain app inputs.

## Required verification

All recurring checks run through `manage.py`. Add platform contract coverage
for every new shared primitive and keep app regression coverage in its app test
module. Before a checkpoint is complete run `python manage.py check` and
`python manage.py test`; runtime, HTTP, realtime, and frontend tests must
exercise every discovered app where the contract is cross-app.
