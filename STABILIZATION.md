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

- Root tests still contain product assertions, production app imports, and
  statically encoded inventories and browser-suite identities.
- Platform code still contains a legacy global CLI, app-specific runtime
  policy, compatibility APIs, and name-aware behavior.
- The shared UI barrel still exposes elements whose independent consumer count
  has not proved a generic boundary.
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
2. **Evacuate monoapp behavior from root tests — pending.**
3. **Remove domain-aware platform code — pending.**
4. **Audit shared libraries — pending.**
5. **Make structural debt measurable — pending.**
6. **Repair central builder internals — pending.**
7. **Repair monoapps independently — pending.**
8. **Activate permanent gates — pending.**

## Next action

Begin checkpoint 2 by inventorying every root test that imports production app
code, asserts product-specific behavior, or encodes a fixed real-app inventory.
Move each assertion to its owning app before replacing central coverage with a
synthetic declarative fixture.
