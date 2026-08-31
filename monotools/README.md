# Internal application platform

`monotools` is the repository's internal platform for independently deployable
FastAPI applications. It is intentionally not a public SDK: abstractions enter
only after more than one app has proved their boundary.

Every top-level module begins with a docstring containing a concise summary, a
blank line, and an explanatory paragraph describing its responsibility and
boundary. Root structural checks enforce this contract, and the repository
cockpit presents the same documentation without maintaining a parallel catalog.

## App contract

Each app declares its name, title, importable FastAPI module, capabilities,
cross-boundary production imports, and frontend artifacts in `app.yaml`. The
import list is the agent-visible inventory of `monotools.*` modules and shared
`@xenorepo/*` packages used by app-owned production source; validation rejects
drift between that declaration and source. Artifact source, output, and format are
independent facts; routes map server-owned URL paths to logical artifact names.
`python manage.py check` discovers every definition, validates its source
contract, imports its service, builds its browser documents, and validates the
resulting `dist/` directory. The service owns `/health`, the API-only OpenAPI
registry at `/agent/tools`, its declared document routes, and its domain routes.
The lifecycle rejects agent operations without unique operation identifiers,
constrained parameter and request schemas, or typed success responses. Bodyless
`204` responses remain explicit contracts. The same check gates ordinary builds,
complete verification, and both verification passes required for repository
promotion.

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

Frontend artifacts export `mount(root)` and are bundled centrally with esbuild.
The required `preact` format accepts only TSX entries, uses Preact's automatic
JSX transform, and imports external CSS. Every artifact is a self-contained document with embedded CSS
and JavaScript and no external runtime assets or separate frontend service.
Monotools validates the complete entry-rooted import graph before mutating
`dist/`, watches app and relevant shared sources, and generates an API-only
OpenAPI declaration in the owning app's ignored `data/` directory before type
checking. Imported modules require no metadata. Use
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

## Monoapp creation and repository promotion

`uv run manage.py monoapp create NAME --title TITLE` renders the canonical
FastAPI, Preact, metadata, specification, agent-context, ignore, and app-owned
test skeleton. Replace the generated product placeholders and acceptance
journey; the template is structure, not a product specification.

When mounted by Xenorepo, every managed app exposes `git status` and
`git create-repo` through `monotools.provisioning`. Promotion requires
explicit `--owner`, `--repository`, and `--visibility` values, a clean Xenorepo
worktree, GitHub CLI authentication, and two successful complete verification
runs. It extracts app-only history, pushes it to GitHub, remounts the same path
as a submodule, and commits Xenorepo's gitlink. Fresh checkouts initialize all
declared app submodules through `uv run manage.py bootstrap`.

A promoted monoapp is independently versioned but deliberately not standalone:
it consumes the enclosing checkout's current Monotools and shared packages.
Standalone execution and a pinned Xenorepo/Monotools dependency are explicitly
deferred until a mature app proves that separate contract. Repository identity
is therefore absent from `app.yaml`, so promotion does not constrain that later
packaging decision.

These repository and structural-audit policies intentionally live in Monotools'
separate provisioning package: standalone monoapp managers expose only generic
lifecycle commands, and the root Xenorepo manager adds provisioning controls
while mounting them.

## Browser verification

`python manage.py ui-check [app]` checks one app or all apps in deterministic
order. Every metadata-declared frontend route receives Monotools' universal
wide/narrow Chromium smoke journey; this proves delivery and self-containment,
reload resilience, baseline document structure, and keyboard reachability—not
product acceptance. New and existing monoapps inherit these checks without
declaring or copying them. Domain scenarios remain in
`apps/<app>/tests/e2e/` and use exactly one proof tag: `acceptance`,
`browser-integration`, `visual`, or `accessibility`. Viewport names never imply
input modality; trusted mouse, native Chromium touch, and keyboard evidence are
separate claims. Synthetic events may support browser-integration tests but
cannot satisfy trusted-input acceptance.

Once an app has a `SPEC.md`, its manager must declare an app-owned browser suite.
This makes promotion from a product plan to a runnable monoapp contingent on an
executable user journey instead of allowing the universal route smoke check to
stand in for the specification's acceptance criteria.

Static TypeScript parsing and Playwright enumeration run before builds or other
browser-lifecycle mutation. Each run retains `summary.json`, `playwright.log`,
`service.log`, the isolated browser database where applicable, and failure
screenshots/traces under `apps/<app>/data/ui-check/`. Pass `--evidence` to retain
trace, video, and HAR output for successful runs. Chromium automation is a
browser-input claim, not evidence about Safari or physical mobile hardware.

The final `aesthetic-check` gate deliberately spends multimodal-model inference
on perceptual quality. Before that call, the universal visual proof renders every
declared route at 1440×1000, 768×1024, and 390×844; rejects horizontal overflow,
clipped or zero-size controls, and text below 9 px; and writes the actual viewport
screenshots to `data/ui-check/aesthetic-screenshots/`. The gate sends the complete
matrix plus optional app-owned `UI.md` direction to the OpenAI Responses API and
retains its structured verdict in `aesthetic-review.json`. `OPENAI_API_KEY` is
mandatory; `MONOTOOLS_AESTHETIC_MODEL` may override the default `gpt-5.5`
reviewer. `verify` runs this AI review last, so a model outage, incomplete matrix,
or major aesthetic finding fails the checkpoint.
