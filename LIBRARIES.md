# Custom Library Catalog

This is the authoritative inventory of reusable libraries owned by this
repository. Add an entry before adopting a new shared library in a monoapp, and
update its contract whenever its public surface changes.

Applications are consumers; they do not import one another.

Repository-specific composition lives in `monotools/provisioning/`, separate
from reusable monoapp orchestration. Provisioning may depend on orchestration
contracts; `monotools.orchestration` must not depend on provisioning policy.

| Library | Language | Location | Public responsibility | Adoption rule |
| --- | --- | --- | --- | --- |
| Monotools | Python + TypeScript tooling | `monotools/`, `tsconfig.preact.json` | Typed metadata, discovery, lifecycle orchestration, build validation, FastAPI runtime, portable persistence, generic transport primitives, and evidence handling. | A capability must be declarative and reusable by an arbitrary future monoapp. |
| Console Preact UI | TypeScript + CSS | `packages/ui/` | Typed shells, panes, rails, and command controls with stable classes and external presentation. | Every component must have at least two independent monoapp consumers. |
| Browser Testing | JavaScript/TypeScript | `packages/browser-testing/` | Shared Playwright fixtures, strict browser diagnostics, trusted input drivers, schema-versioned evidence, and static proof validation. | Shared code contains no app routes, selectors, entities, or gesture semantics. |

## Console Preact UI contract

The typed `ConsoleShell`, `UtilityRail`, `StatusRail`, `ConsolePane`, and
`CommandButton` components each have nine independent consumers. `EmptyState`
has three and owns only centered empty-result geometry around an app-owned heading
and optional detail. `Modal` has two independent consumers and owns accessible
dialog structure, Escape dismissal, and direct-backdrop dismissal while leaving
content and backdrop presentation app-owned except for the shared subtle corner
radius. Rectangular inputs and textareas within the shared shell use the same
radius, while textareas never expose native drag resizing. Component props extend
the corresponding Preact native
HTML attributes, named props replace slots, and stable `x-ui-*` classes are the
styling boundary. Console colors remain application-owned through the documented
`--console-*` custom properties, including rail background and border overrides.
The package owns only proved console geometry and interaction treatment; app
layout remains in external app-owned CSS. All consumers import `@xenorepo/ui`.
Established catalogued controls are the default for matching semantics. The
independent-consumer rule governs creating abstractions, not consuming them.

## Monotools production contract inventory

Application metadata is authoritative for direct cross-boundary production
imports. Public modules not listed here are Monotools implementation details or
root orchestration surfaces rather than independently adopted app contracts.

| Public module | Independent consumer count |
| --- | ---: |
| `monotools.integrations.commerce` | 1 |
| `monotools.integrations.mailer` | 1 |
| `monotools.integrations.stripe` | 1 |
| `monotools.orchestration.lifecycle` | 1 |
| `monotools.orchestration.management` | 9 |
| `monotools.persistence.auth` | 2 |
| `monotools.persistence.database` | 6 |
| `monotools.persistence.orm` | 2 |
| `monotools.runtime.appkit` | 7 |
| `monotools.runtime.application` | 9 |
| `monotools.runtime.http` | 7 |
| `monotools.runtime.realtime` | 3 |

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
