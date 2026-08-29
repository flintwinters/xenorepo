# Custom Library Catalog

This is the authoritative inventory of reusable libraries owned by this
repository. Add an entry before adopting a new shared library in a monoapp, and
update its contract whenever its public surface changes.

Applications are consumers; they do not import one another.

| Library | Language | Location | Public responsibility | Adoption rule |
| --- | --- | --- | --- | --- |
| Monotools | Python + TypeScript tooling | `monotools/`, `tsconfig.frontend.json` | Typed metadata, discovery, lifecycle orchestration, build validation, FastAPI runtime, portable persistence, generic transport primitives, and evidence handling. | A capability must be declarative and reusable by an arbitrary future monoapp. |
| Console Preact UI | TypeScript + CSS | `packages/ui/` | Typed shells, panes, rails, and command controls with stable classes and external presentation. | Every component must have at least two independent monoapp consumers. |
| Console Lit UI | TypeScript | `packages/lit-ui/` | Construction primitives for shells, panes, rails, controls, status, shared form treatment, design tokens, and browser-artifact chrome. | Every custom element must have at least two independent monoapp consumers. |
| Browser Testing | JavaScript/TypeScript | `packages/browser-testing/` | Shared Playwright fixtures, strict browser diagnostics, trusted input drivers, schema-versioned evidence, and static proof validation. | Shared code contains no app routes, selectors, entities, or gesture semantics. |

## Console Lit UI contract

The package has one named JavaScript export, `consoleControls`, used by two
independent monoapps. Importing the package also registers these proved custom
elements:

| Custom element | Independent consumer count |
| --- | ---: |
| `x-console-shell` | 2 |
| `x-utility-rail` | 2 |
| `x-status-rail` | 2 |
| `x-console-pane` | 2 |
| `x-command-button` | 2 |

`consoleControls` has two independent consumers. Identities remain app-owned
and discoverable from metadata; central policy records only the evidence count.
All consumers import the package boundary as `@xenorepo/lit-ui`.

## Console Preact UI contract

The typed `ConsoleShell`, `UtilityRail`, `StatusRail`, `ConsolePane`, and
`CommandButton` components each have four independent consumers. `EmptyState`
has two and owns only centered empty-result geometry around an app-owned heading
and optional detail. Component props extend the corresponding Preact native
HTML attributes, named props replace slots, and stable `x-ui-*` classes are the
styling boundary. The package owns only proved console geometry and interaction
treatment; app layout remains in external app-owned CSS. All consumers import
`@xenorepo/ui`.

## Monotools production contract inventory

Application metadata is authoritative for direct cross-boundary production
imports. Public modules not listed here are Monotools implementation details or
root orchestration surfaces rather than independently adopted app contracts.

| Public module | Independent consumer count |
| --- | ---: |
| `monotools.appkit` | 7 |
| `monotools.auth` | 2 |
| `monotools.commerce` | 1 |
| `monotools.database` | 6 |
| `monotools.http` | 7 |
| `monotools.lifecycle` | 1 |
| `monotools.mailer` | 1 |
| `monotools.management` | 9 |
| `monotools.orm` | 2 |
| `monotools.realtime` | 3 |
| `monotools.runtime` | 9 |

Single-consumer modules are narrow typed integration contracts, not extracted
domain implementations. A second consumer is required before application
behavior may move into them.

## Browser Testing contract inventory

| Public surface | Independent monoapp suite count |
| --- | ---: |
| `test`, `expect` | 6 |
| `installInputEvidence`, `readInputEvidence`, `validateInputEvidence`, `touchPath` | 2 |
| `acknowledgeHttpFailures` | 1 |
| `EVIDENCE_SCHEMA_VERSION`, `keyboardSequence`, `mousePath` | 0 |
| `@xenorepo/browser-testing/validate` executable | 0 |

Zero-consumer surfaces are framework-owned proof primitives characterized by
the central synthetic browser suite or invoked by Monotools orchestration; they
do not encode product behavior. The one-consumer HTTP acknowledgement remains
generic failure-accounting policy and is covered by the central fixture.

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
