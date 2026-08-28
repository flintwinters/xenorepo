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

The stabilization campaign begins with these known categories. Counts become
authoritative when the read-only audit command is introduced at checkpoint 5.

- Root tests now use invented fixture apps or runtime-discovered values; product
  assertions, production imports, and owned suite identities have been removed
  from the central suite and preserved beside their owning monoapps.
- Platform lifecycle and management code is generic: app managers own product
  runtime policy, and the legacy global CLI and compatibility views are gone.
- Shared-library exports and their independent consumer counts are inventoried
  in `LIBRARIES.md`; the shared UI surface contains only proved elements.
- Central and app-owned Python, TypeScript, JavaScript, and source HTML include
  files or functions beyond the intended size and complexity limits.
- Lifecycle, metadata, browser-validation, migration, watching, and UI-runner
  internals require decomposition while preserving their observable contracts.
- Several app-owned controllers, transactions, and realtime or process handlers
  require independent characterization and simplification.

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
5. **Make structural debt measurable — pending.**
6. **Repair central builder internals — pending.**
7. **Repair monoapps independently — pending.**
8. **Activate permanent gates — pending.**

## Next action

Begin checkpoint 5 by adding a stable, read-only architecture and structural
audit to root `manage.py`, recording exact violation counts, and driving the
initial architecture inventory to zero without yet repairing the large
platform and monoapp internals assigned to later checkpoints.
