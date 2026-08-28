# Custom Library Catalog

This is the authoritative inventory of reusable libraries owned by this
repository. Add an entry before adopting a new shared library in a monoapp, and
update its contract whenever its public surface changes.

Applications are consumers; they do not import one another.

| Library | Language | Location | Public responsibility | Adoption rule |
| --- | --- | --- | --- | --- |
| Monotools | Python + TypeScript tooling | `monotools/`, `scripts/check-lit.mjs`, `tsconfig.frontend.json` | Typed metadata, discovery, lifecycle orchestration, build validation, FastAPI runtime, portable persistence, generic transport primitives, and evidence handling. | A capability must be declarative and reusable by an arbitrary future monoapp. |
| Console Lit UI | TypeScript | `packages/lit-ui/` | Construction primitives for shells, panes, rails, controls, status, shared form treatment, design tokens, and browser-artifact chrome. | Every custom element must have at least two independent monoapp consumers. |
| Browser Testing | JavaScript/TypeScript | `packages/browser-testing/` | Shared Playwright fixtures, strict browser diagnostics, trusted input drivers, schema-versioned evidence, and static proof validation. | Shared code contains no app routes, selectors, entities, or gesture semantics. |

## Extraction rules

- A library has a narrow, typed public contract and no imports from a monoapp.
  Domain models, repositories, routes, and product behavior remain app-owned.
- Backend libraries expose transport and persistence primitives only after at
  least two independent monoapps prove the boundary.
- Frontend libraries live under `packages/`, are imported through their package
  name, and must not embed a monoapp's API paths, state, copy, or workflow.
- Keep frontend artifact sources in `apps/<app>/frontend/` and backend/domain
  code in `apps/<app>/backend/`. A monoapp root contains only administrative,
  structural, entrypoint, and informational files; `manage.py` is its only
  Python file. FastAPI is the sole service delivering the built frontend and API.
- Add framework-level tests for every shared contract; retain product behavior
  tests in the owning monoapp's suite.
- Remove or return a shared custom element to its owner when fewer than two
  independent monoapps prove its generic boundary.

## ORM template policy

- Shared ORM templates own infrastructure facts and schema invariants;
  monoapps retain independent declarative bases, metadata, and databases.
- Monoapps extend templates with foreign keys and domain facts. They never
  import another monoapp's models, and complete domain tables stay app-owned.
- Metadata conformance tests enforce canonical column names, types, lengths,
  nullability, and primary keys while permitting domain-specific extensions.
- Similar-looking app-owned tables remain local until independent consumers
  prove the exact shared contract.
- Template changes may intentionally break older consumers until preserving
  deployed data makes migration compatibility economically justified. Current
  templates are the supported baseline; monoapps are brought forward deliberately.
