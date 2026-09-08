# Universal monoapp code reuse review

Source review implemented 2026-09-08. This review includes only changes that
apply to every active monoapp. `LIBRARIES.md` remains authoritative for adopted
contracts and extraction policy.

## Scope and conclusion

All eight active monoapps have a root `manage.py`, an `app.yaml`, a FastAPI
runtime created by Monotools, a Python suite, and an app-owned browser suite.
The migration places lifecycle declarations in metadata, binds each runtime to
its owning definition, and makes central validation own universal artifact
assertions.

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

Implementation: typed lifecycle-test metadata in `app.yaml` lets
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

Implementation: a generic local runtime constructor accepts `__file__`, resolves
the owning `app.yaml` from `backend/server.py`, and delegates to the existing
application assembly. `create_local_application(__file__)` returns exactly what
`create_application(name)` returns. Every server and the scaffold template use
the local constructor. Name-based construction remains a lower-level
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
browser suite. Before this migration, the scaffold and several mature app suites
repeated self-contained frontend assertions already enforced by those central
paths.

Implementation: central tests and root `check` own invariants that apply
identically to every discovered monoapp. The scaffold and app suites no longer
repeat those assertions, and central checks demonstrate that each discovered
definition is included. App suites retain domain contracts,
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
