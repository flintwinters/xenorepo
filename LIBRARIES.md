# Custom Library Catalog

This is the authoritative inventory of reusable libraries owned by this
repository. Add an entry before adopting a new shared library in an app, and
update its contract here whenever its public surface changes. Applications are
consumers; they do not import one another.

| Library | Language | Location | Public responsibility | Consumers |
| --- | --- | --- | --- | --- |
| Monotools | Python | `monotools/` | `monotools.apps`, `monotools.lifecycle`, `monotools.runtime`, `monotools.database`, `monotools.auth`, `monotools.http`, and `monotools.realtime`: declarative discovery, lifecycle commands, FastAPI document runtime, portable SQLAlchemy setup and database URL resolution, opaque credentials, HTTP/session primitives, and WebSocket delivery. | Central `manage.py` and all apps as applicable. |
| Console Lit UI | TypeScript | `packages/lit-ui/` | Reusable Lit console elements, design tokens, and chrome for browser artifacts. | Calculator today; new Lit pages. |

## Extraction rules

- A library has a narrow, typed public contract and no imports from an
  application. App-specific domain models, repositories, routes, and product
  behavior remain inside that app. Applications are consumers; they do not
  import one another.
- Backend libraries live in Python packages and expose transport/persistence
  primitives only after at least two applications prove the boundary.
- Frontend libraries live under `packages/`, are imported through their package
  name, and must not embed an app's API paths, state, or copy.
- Keep frontend artifact sources in `apps/<app>/frontend/` and backend/domain
  code in the application package root. FastAPI remains the sole service that
  delivers the built frontend and the app API.
- Add framework-level tests for every shared contract; retain product behavior
  tests in the consuming app's test module.
