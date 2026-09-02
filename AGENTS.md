# Centralized App Monotools Laboratory

## 1. Guiding motivation

Monotools is the primary product; monoapps prove its planning, creation,
lifecycle, validation, and maintenance workflows. Optimize for coherence,
determinism, reusable automation, short feedback loops, and actionable failures.
Promote recurring operations and protections into Monotools.

Before implementation, review the system outcome, actors, responsibilities,
invariants, states, dependencies, adjacent behavior, and lifecycle. Compare
inaction, existing mechanisms, and the simplest adequate intervention by
coherence, reversibility, blast radius, and maintenance. Cover malformed,
unavailable, repeated, interrupted, and recovery states. Reject misplaced
responsibility, exposed implementation accidents, invalid intermediate states,
and lost recovery. State the evidence, weakest assumption, and reversal test.

The **monorepo** is this repository, a **monoapp** is one app, and **Monotools**
is the orchestration library.

## 2. Architecture and invariants

- Root `manage.py` is the sole routine entrypoint, exposing Typer/Rich commands
  for every app and recurring workflow.
- Monoapps declare typed metadata and capabilities; Monotools owns discovery,
  scaffolding, lifecycle, build, validation, tests, and status reporting.
- Monotools uses documented, recursively discovered `orchestration`, `runtime`,
  `persistence`, and `integrations` packages.
- Treat every public and control-plane boundary as a product contract.
  Foreseeable repository, configuration, dependency, and runtime states must
  produce coherent, contextual behavior with bounded blast radius. Preserve
  unrelated work, observability, and canonical recovery controls; reserve raw
  crashes for genuine programmer defects.
- Plan a new monoapp in `apps/<app>/SPEC.md` as a shippable walking skeleton
  with real-world validation criteria before implementation.
- Before creation, ask close-ended questions until the walking-skeleton spec and
  acceptance criteria are decision-complete; then run the creation routine and
  customize its generated files in place.
- Each monoapp separates `frontend/` and `backend/`; its root contains only
  administration and information, with `manage.py` as its sole Python file and
  a standalone-deployment README.
- FastAPI is each app's only runtime service. App YAML maps server URLs to
  compiled, self-contained `dist/` HTML; HTML is never source. Monotools compiles
  strict Preact TSX entries with external CSS or immutable allowlisted MonoForm
  pages. Prefer MonoForm for conventional CRUD after a suitability review;
  product-defining or unsupported interactions remain app-owned. Do not add
  frontend services, private Node projects, or build scripts.
- Persist durable facts through SQLAlchemy ORM, defaulting locally to SQLite with
  PostgreSQL-compatible models and transactions. Preserve identifiers,
  timestamps, provenance, transitions, relationships, constraints, and indexes;
  derive projections and migrate repeatably.
- Keep framework code modular and DRY; extract abstractions only after an app
  proves the boundary. Apps share Monotools and contracts, not app source or
  artifacts.
- Reintegrate proven tools and protections into Monotools; consolidate duplicates.
- Operations are deterministic, composable, and reversible where practical.
  Validate before mutation, report partial failures and recovery, and claim
  success only after stable readiness.
- Route all repeatable validation through root `manage.py`. Test in visible,
  ignored per-app `data/`, never hidden directories or `/tmp`. Finish every
  monoapp checkpoint with `uv run manage.py verify`; leaf checks are diagnostic.
- Keep source files under 600 lines and cyclomatic complexity at most 8. Do not
  hide project state or put exposition in UI elements.

## 3. Current tasks

- Preserve Preact-only architecture gates and deterministic app-owned wide/narrow
  visual checks; generate their image baselines locally without versioning them.
- Keep MonoForm a narrow secure CRUD default, not an authorization layer or a
  substitute for app-owned workflows and server-side invariants.
- Enforce the dependency direction `monoapp -> generic Monotools contract`,
  with no static monoapp identity or product policy in central code or tests.
- Admit shared code only after independent consumers prove a generic boundary;
  keep `LIBRARIES.md` authoritative for contracts and extraction policy.
- Keep the active checkpoint and next action concise in `PREACT_MIGRATION.md`.
- Create monoapps from the Monotools template and promote mature apps to
  independently versioned GitHub submodules without weakening their verified
  dependency on the enclosing Xenorepo platform.
