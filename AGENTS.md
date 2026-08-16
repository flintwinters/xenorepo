# Centralized App Tooling Laboratory

## 1. Guiding motivation

This iteration treats centralized tooling as the primary product. Individual
apps are experiments and proving grounds for an impeccable scripting framework
that manages their complete lifecycle: planning, creation, startup, building,
validation, testing, and maintenance.

Optimize first for a coherent developer experience, deterministic behavior,
and reusable automation. App work should expose requirements for the framework;
it should not accumulate one-off scripts or workflows. Promote every proven
operation into shared tooling so each new app becomes easier to understand and
manage than the last.

Prefer short feedback loops, strict contracts, portable state, reproducible
checks, and actionable diagnostics. Observability is part of correctness: fail
early, exit nonzero, identify the cause with evidence, and never report success
before the requested outcome is proved.

When a systemic issue, which may occur more than once, is found, routinize protections against it with scripts orchestrated by manage.py

## 2. Architecture and invariants

- `manage.py` is the sole routine entrypoint and the repository's primary
  interface. Every recurring workflow belongs behind a clear, discoverable
  command implemented with Typer and presented with Rich.
- Central tooling owns planning, scaffolding, discovery, startup, shutdown,
  building, validation, testing, and status reporting. Apps declare facts and
  capabilities; they do not duplicate lifecycle orchestration.
- App definitions are declarative, typed, and capability-driven. Tooling must
  discover behavior from metadata rather than hard-coded app names or implicit
  directory knowledge.
- Applications use FastAPI as their sole runtime service. TypeScript frontends
  are compiled entirely ahead of time into each application's `./dist/`
  directory, which FastAPI routes and serves directly. Do not run a separate
  frontend development or production service such as Vite; startup exposes the
  complete application through one FastAPI service.
- Treat persistence as an implementation detail behind a durable domain
  boundary. Use SQLAlchemy's ORM as the database abstraction layer so
  application behavior, schemas, and lifecycle tooling do not depend on
  backend-specific SQL or connection APIs. Prefer SQLite as the primary
  database, especially for demos and local experiments, while designing models,
  migrations, queries, and transaction boundaries to remain compatible with a
  future PostgreSQL deployment.
- Treat persisted data as a durable information model, never as a snapshot of
  the current screen. Retain domain facts at the highest useful fidelity:
  stable identifiers, precise timestamps, provenance, state transitions, and
  explicit relationships. Model distinct entities, events, and associations in
  typed tables with constraints, foreign keys, and query-driven indexes; avoid
  opaque blobs, overloaded columns, and duplicated derived values when the
  underlying facts have known structure.
- Normalize pragmatically to prevent ambiguity and update anomalies, not to
  satisfy a theoretical form mechanically. Preserve canonical source facts and
  derive projections from them. Denormalize only for a demonstrated query need,
  with an explicit source of truth and a deterministic rebuild path. Evolve
  schemas through repeatable migrations that retain existing information.
- Framework code is modular and DRY. Build shared functions and modules around
  clear responsibilities, and promote an abstraction only after concrete app
  work has demonstrated the shared boundary.
- Operations are deterministic, composable, and reversible where practical.
  Generated artifacts record their inputs, state is explicit, and partial
  failures produce useful recovery instructions.
- Validation is layered but centrally orchestrated. Maintain project-specific
  testing infrastructure and expose every routine check through `manage.py`;
  do not add ad-hoc test commands or scripts.
- Lifecycle operations fail early, hard, and visibly. Check preconditions before
  mutation, prove stable readiness before success, preserve relevant process
  output, and report cleanup failures without hiding the original error.
- Test directly in the repository. Ignored runtime and test state belongs in
  the visible per-app `data/` directory, never a hidden directory or `/tmp`.
- Keep source files below 600 lines and cyclomatic complexity at or below 8.
  Prefer small modules with explicit responsibilities and strict interfaces.
- Apps remain independent product experiments. They may share central tooling,
  contracts, and learned patterns, but not application source or build artifacts.
- Give every app a README so it can be deployed as a standalone submodule.
- Do not use hidden folders or hide state or project files.
- Do not put exposition in UI elements.

## 3. Current tasks

- Repair and verify WIRE/98 live synchronization across Starlette worker threads,
  ensuring streaming generators never yield while holding thread-owned locks.
