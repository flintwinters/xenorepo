# Universal monoapp code reuse review

Source review, 2026-09-08. This review includes only opportunities that apply to
every active monoapp. `LIBRARIES.md` remains authoritative for adopted contracts
and extraction policy.

## Scope and conclusion

All eight active monoapps have a root `manage.py`, an `app.yaml`, a FastAPI
runtime created by Monotools, a Python suite, and an app-owned browser suite.
Only two remaining implementation patterns are duplicated across that complete
set: lifecycle declaration in each manager and runtime identity binding in each
server. A third opportunity is to remove app-owned tests of platform invariants
after the central checks prove them for every app.

Frontend HTTP clients, database fixtures, form controls, realtime code, and
domain error handling are excluded. They have multiple consumers, but they do
not apply to every monoapp. Root command selection is also excluded because it
belongs to Xenorepo composition rather than monoapps.

## 1. Make lifecycle suites declarative metadata

Evidence: every `apps/*/manage.py` imports `create_app_manager`, calls it with
`__file__`, declares `tests="tests"`, declares one browser-suite path and proof
kinds, exports `manager.app`, and invokes that app under `__main__`. The current
shared implementation in `monotools/orchestration/management.py` already owns
all command behavior. The per-app files differ only in declaration values such
as the suite filename, visual-proof requirement, and trusted input modalities.
The scaffold reproduces the same wrapper in
`monotools/templates/monoapp/manage.py.template`.

Proposal: add typed lifecycle-test metadata to `app.yaml` and let
`create_app_manager(__file__)` resolve the standard Python suite, browser suite,
proof kinds, viewports, and input modalities from the local definition. Keep a
narrow explicit override API only if an independently deployed monoapp needs it.
The leaf `manage.py` remains the sole Python entrypoint, but becomes the same
stable adapter for every app.

This removes duplicated authoritative knowledge: proof requirements currently
live in Python while application capabilities, artifacts, and routes live in
YAML. It also makes suite validation available during metadata loading without
executing an app manager module.

Weakest assumption: lifecycle evidence is part of application metadata rather
than executable manager policy. Reject the move if suite declaration needs
runtime computation; no current consumer does. The reversal test is simple:
the old explicit arguments can be restored without changing suite files or
command behavior.

Validate metadata rejection for missing, absolute, escaping, malformed, and
incompatible suite declarations. Exercise every leaf command and root discovery,
then finish with `uv run manage.py verify`.

## 2. Bind a runtime to its local definition instead of repeating its name

Evidence: every `apps/*/backend/server.py` calls
`monotools.runtime.application.create_application` with its own static app name.
Simple apps assign the result directly; richer apps make the same call inside a
`create_app` factory before adding domain routes and dependencies. The manager
side already has the analogous local-resolution contract:
`resolve_local_app(manage_file)` loads the definition beside `manage.py`.

Proposal: add a generic local runtime constructor that accepts `__file__`, walks
from `backend/server.py` to the owning `app.yaml`, and delegates to the existing
application assembly. For example, `create_local_application(__file__)` should
return exactly what `create_application(name)` returns today. Migrate every
server and the scaffold template. Keep name-based construction as a lower-level
API where central orchestration legitimately starts an app by metadata identity.

This removes the repeated identity string and makes the filesystem ownership
boundary authoritative. Renaming or moving a monoapp can no longer leave a
server silently bound to another definition. The implementation should reuse
the existing definition loader rather than introduce another YAML parser or app
registry.

Weakest assumption: production server modules remain beneath their monoapp
directory, which is already an architectural invariant. Reject upward search
that can cross into another app or the repository root without finding the
immediate owning definition. The reversal test is replacing the local call with
the explicit name; domain factories and routes remain unchanged.

Validate direct and factory-based servers, missing metadata, a malformed
definition, a path outside a monoapp, symlinks, and a mismatch between module
location and declared module. Run the central application tests and every app
suite through the root entrypoint.

## 3. Keep universal platform assertions in central validation

Evidence: every app receives health, agent-tool metadata, document routes,
build validation, self-contained artifact validation, wide/narrow route smoke,
and lifecycle commands from Monotools. These are platform contracts implemented
by `monotools/runtime/application.py`, lifecycle orchestration, and the universal
browser suite. Scaffolded app tests nevertheless begin with an app-owned test of
self-contained frontend output in
`monotools/templates/monoapp/tests/test_app.py.template`, and some mature suites
retain variants of that platform assertion.

Proposal: make central tests and root `check` the exhaustive owner of invariants
that apply identically to every discovered monoapp. Remove those assertions from
the scaffold and app suites only after the central checks demonstrate that each
discovered definition is included. App suites should retain domain contracts,
custom build behavior, and product-specific accessibility or visual evidence.

This reuses the existing validation path and prevents platform rules from
drifting into slightly different app-owned assertions. It is a deletion and
ownership correction, not a new test base class or shared assertion library.

Weakest assumption: root validation is always part of the supported verification
workflow, including independently versioned submodules. Preserve a small
standalone platform-contract suite exposed by Monotools if a monoapp must verify
outside Xenorepo. The reversal test is restoring the generated smoke test without
changing application code.

Before deletion, prove discovery coverage, failure attribution, malformed and
missing artifacts, external script and stylesheet references, health behavior,
and both configured viewports. Finish with `uv run manage.py verify`.

## Recommended order

Implement local runtime binding first because it is narrow and removes a real
identity mismatch state. Move manager declarations to typed metadata second;
this changes the application-definition contract and should be done atomically
with templates and all consumers. Consolidate universal tests last, after the
first two contracts have central coverage.

Do not create a universal frontend, persistence, transport, or domain layer.
There is no implementation boundary in those areas shared by all current
monoapps, and forcing one would couple independently changing products.
