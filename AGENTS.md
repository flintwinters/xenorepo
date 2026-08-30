# Centralized App Monotools Laboratory

## 1. Guiding motivation

Monotools is the primary product; monoapps are experiments that prove its
planning, creation, lifecycle, validation, and maintenance workflows. Optimize
for a coherent developer experience, deterministic behavior, reusable
automation, short feedback loops, and actionable failures. Promote recurring
operations and protections into Monotools instead of accumulating app-specific
scripts.

Make owner-level decisions for the whole outcome, not the requested task.
Identify the real objective and
binding constraint; compare inaction, existing solutions, and the simplest
adequate intervention. Allocate resources by expected value and opportunity
cost. Move quickly on reversible choices, preserve optionality around
commitments, and test uncertainty that could change the decision. Consider
execution risk, failure modes, and second-order effects; prefer systems that
eliminate recurring work, and state evidence that would reverse the choice.

Terminology: the **monorepo** is this repository, a **monoapp** is an app within
it, and **Monotools** is the canonical orchestration library.

## 2. Architecture and invariants

- Root `manage.py` is the sole routine entrypoint. It exposes discoverable
  Typer/Rich commands for every app and recurring workflow.
- Monoapps declare typed metadata and capabilities; Monotools owns discovery,
  scaffolding, lifecycle, build, validation, tests, and status reporting.
- Monotools uses `orchestration`, `runtime`, `persistence`, and
  `integrations` packages; every module is documented and recursively discovered.
- Plan a new monoapp in `apps/<app>/SPEC.md` as a shippable walking skeleton
  with real-world validation criteria before implementation.
- Each monoapp separates `frontend/` and `backend/`; its root contains only
  administration, structure, entrypoints, and information. Its sole root-level
  Python file is `manage.py`, and it has a standalone-deployment README.
- FastAPI is each app's only runtime service. App YAML maps server-owned URLs to
  self-contained compiled `dist/` HTML artifacts; HTML is never application
  source. Frontend entries are strict Preact TSX with external CSS, compiled by
  Monotools. Do not add separate frontend services, private Node projects, or
  build scripts.
- Persist durable domain facts through SQLAlchemy ORM, with SQLite as the local
  default and PostgreSQL-compatible models and transaction boundaries. Preserve
  identifiers, timestamps, provenance, transitions, relationships, constraints,
  and indexes; derive projections and migrate schemas repeatably.
- Keep framework code modular and DRY, but extract abstractions only after an
  app proves the shared boundary. Apps may share Monotools and contracts, not
  application source or build artifacts.
- Reintegrate proven findings, tools, and protections into the Xenorepo and
  Monotools core; consolidate duplicates so every app improves shared foundations.
- Operations must be deterministic, composable, and reversible where practical.
  Validate preconditions before mutation, report partial failures and recovery
  steps, and never claim success before readiness is stable.
- Route all repeatable validation through root `manage.py`. Test in visible,
  ignored per-app `data/`, never hidden directories or `/tmp`. Finish every
  monoapp checkpoint with `uv run manage.py verify`; leaf checks are diagnostic.
- Keep source files under 600 lines and cyclomatic complexity at most 8. Do not
  hide project state or put exposition in UI elements.

## 3. Current tasks

- Keep the completed Preact-only architecture gates permanent.
- Keep deterministic app-owned wide/narrow visual baselines; do not redesign.
- Enforce the dependency direction `monoapp -> generic Monotools contract`,
  with no static monoapp identity or product policy in central code or tests.
- Admit shared code only after independent consumers prove a generic boundary;
  keep `LIBRARIES.md` authoritative for contracts and extraction policy.
- Keep the active checkpoint and next action concise in `PREACT_MIGRATION.md`
  so work can resume safely after context clearing.
- Create monoapps from the Monotools template and promote mature apps to
  independently versioned GitHub submodules without weakening their verified
  dependency on the enclosing Xenorepo platform.
