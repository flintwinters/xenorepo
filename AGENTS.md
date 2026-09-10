# Centralized App Monotools Laboratory

## 1. Guiding motivation

Monotools is the product; monoapps prove its lifecycle. Optimize for coherence,
determinism, reusable automation, short feedback, and actionable failures.

Before implementation, review outcomes, responsibilities, invariants, states,
dependencies, and lifecycle. Compare inaction, existing mechanisms, and the
simplest adequate intervention by reversibility, blast radius, and maintenance.
Cover malformed, unavailable, repeated, interrupted, and recovery states. Reject
misplaced responsibility, invalid intermediate states, and lost recovery.

## 2. Architecture and invariants

- Root `manage.py` is the sole routine entrypoint for every recurring workflow.
- Monoapps declare typed metadata, capabilities, and lifecycle evidence. Their
  managers and runtimes resolve the owning definition from local entrypoints;
  Monotools owns discovery, scaffolding, lifecycle, build, validation, universal
  platform tests, and status reporting.
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
  strict Preact TSX entries with external CSS. Forms are app-owned compositions
  of MonoUI primitives using generated OpenAPI types; backend models, validation,
  and authorization remain authoritative. Do not add
  frontend services, private Node projects, or build scripts.
- Persist durable facts through SQLAlchemy ORM, defaulting locally to SQLite with
  PostgreSQL-compatible models and transactions. Preserve identifiers,
  timestamps, provenance, transitions, relationships, constraints, and indexes;
  derive projections and migrate repeatably.
- Keep framework code modular and DRY; extract abstractions only after an app
  proves the boundary. Apps share Monotools and contracts, not app source or
  artifacts.
- Reintegrate proven tools and protections into Monotools.
- Operations are deterministic, composable, and reversible.
  Validate before mutation, report partial failures and recovery, and claim
  success only after stable readiness.
- Tools and source are independent: `restore` installs Python/Node tools,
  `bootstrap` adds browsers, and `monoapp initialize` populates source.
  `monoapp fork-workspace` builds its selection and atomically focuses inventory.
- Route all repeatable validation through root `manage.py`. Test in visible,
  ignored per-app `data/`, never hidden directories or `/tmp`. Use `verify` for
  fast inner-loop checks and `release` for slow browser and fail-closed dependency
  security gates before mainline release; leaf checks are diagnostic.
- Keep source files under 600 lines and cyclomatic complexity at most 8. Do not
  hide project state or put exposition in UI elements.

- Apps and Monotools remain deployment-independent; infrastructure execution and
  provider adapters stay external behind a generic operator protocol.

## 3. Current tasks

- Make the runtime boundary proposed in `DEPLOYMENT.md` explicit and testable
  without introducing deployment knowledge into apps or Monotools.
- Preserve Preact-only gates and app-owned wide/narrow visual checks; generate
  baselines locally without versioning them.
- Enforce the dependency direction `monoapp -> generic Monotools contract`,
  with no static monoapp identity or product policy in central code or tests.
- Admit shared code only after independent consumers prove a generic boundary;
  keep `LIBRARIES.md` authoritative for contracts and extraction policy.
- Create from the Monotools template and promote mature apps first to local Git
  repositories; configure hosted remotes manually without weakening their verified
  Xenorepo dependency.
