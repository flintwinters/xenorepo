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
maximum of 8 for Python, TypeScript, JavaScript, and source HTML functions.

The checkpoint 5 baseline is:

- Architecture: 0 violations across central identity isolation, cross-app
  imports, frontend package boundaries, and shared custom-element adoption.
- File size: 3 violations, all app-owned; central/shared code has 0.
- Function complexity: 31 violations: 14 in root/shared platform code and 17
  in app-owned code.

- Root tests now use invented fixture apps or runtime-discovered values; product
  assertions, production imports, and owned suite identities have been removed
  from the central suite and preserved beside their owning monoapps.
- Platform lifecycle and management code is generic: app managers own product
  runtime policy, and the legacy global CLI and compatibility views are gone.
- Shared-library exports and their independent consumer counts are inventoried
  in `LIBRARIES.md`; the shared UI surface contains only proved elements.
- Central and app-owned Python, TypeScript, JavaScript, and source HTML have the
  exact size and complexity debt recorded above.
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
5. **Make structural debt measurable — complete.** Root `audit` reports stable
   architecture, file-size, and cross-language cyclomatic inventories without
   mutation. Root `check` and therefore `verify` reject architecture drift while
   reporting structural debt for the next two checkpoints. The initial
   architecture violation was removed, the inventory is locked by synthetic
   and repository-level tests, and the complete verification matrix passed on
   2026-08-28.
6. **Repair central builder internals — pending.**
7. **Repair monoapps independently — pending.**
8. **Activate permanent gates — pending.**

## Next action

Begin checkpoint 6 by decomposing the 14 recorded root/shared-platform complex
functions to complexity 8 or lower without changing lifecycle commands,
diagnostics, failure behavior, browser evidence, or artifact contracts. Keep
the 3 app-owned large files and 17 app-owned complex functions unchanged for
checkpoint 7.
