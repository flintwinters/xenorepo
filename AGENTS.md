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
  `.state/`, never `/tmp`.
- Keep source files below 600 lines and cyclomatic complexity at or below 8.
  Prefer small modules with explicit responsibilities and strict interfaces.
- Apps remain independent product experiments. They may share central tooling,
  contracts, and learned patterns, but not application source or build artifacts.

## 3. Current tasks

1. Keep the app catalog empty until the next proving-ground experiment is selected.
2. Add centrally orchestrated browser testing to `manage.py` when an app again
   requires interaction and responsive-layout coverage.
3. Continue implementing lifecycle operations one verified logical checkpoint
   at a time, committing each checkpoint with a detailed message.
