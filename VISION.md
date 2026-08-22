# Monotools Vision

## The destination

Xenorepo is a durable laboratory for building small, excellent applications
and the platform that makes them repeatable.

The long-term product is not a collection of unrelated demos. It is a coherent
application workshop: an operator can describe an application, scaffold it,
run it, inspect it, test it, and deploy it through one predictable interface.
Each experiment should leave the workshop better than it found it by proving a
reusable contract, library, or lifecycle operation.

Monotools should make the default path the reliable path. A new application
should declare its identity, capabilities, frontend artifacts, routes, and
runtime facts. The platform should then discover those facts and provide the
rest: planning, creation, build composition, validation, startup, shutdown,
browser verification, diagnostics, and status. Applications own their domain
behavior; Monotools owns the repeatable machinery around it.

The resulting experience should feel like a well-designed instrument:

- deterministic enough to trust in automation;
- observable enough to diagnose without guesswork;
- modular enough to evolve without coupling applications together;
- portable enough to move from local SQLite experiments toward PostgreSQL;
- polished enough that the applications are useful proving grounds, not throwaway toys.

## What we are trying to achieve

### One application contract

Declarative, typed metadata is the boundary between an app and the platform.
The contract should answer what an app is, what it serves, what it can do, and
what it needs to build and run. The platform must not infer behavior from app
names, directory accidents, or duplicated scripts.

### One lifecycle cockpit

`manage.py` is the repository's operational interface. Every recurring action
belongs behind a discoverable Rich/Typer command with clear preconditions,
nonzero failure behavior, preserved evidence, and reversible cleanup. A user
should not need to remember a separate server, frontend, or test workflow for
each application.

### One service boundary

FastAPI is the sole application service. It serves the built document and the
domain API from the same app-owned runtime, with platform health and metadata
contracts alongside app routes. There is no second frontend service to drift
out of sync with the backend.

### Durable domain truth

SQLite remains the practical local default, while ORM, schemas, migrations, and
transactions preserve a reliable path to PostgreSQL.

Longer term, app YAML should be able to declare durable ORM schema intent and
reusable table capabilities, with Monotools producing conventional typed
SQLAlchemy models and Alembic migrations rather than introducing a separate
runtime persistence system.

### A shared, restrained interface language

The central Lit UI package should provide the reusable primitives and visual
language for new pages. The Gruvbox operator-console direction is a product
constraint, not decoration: dense information, clear hierarchy, semantic color,
responsive topology, and self-contained artifacts should make
each application feel like part of one instrument.

### Evidence-driven quality

Validation should operate at several layers without becoming fragmented:
metadata and imports, production builds, Python behavior, HTTP and realtime
contracts, and real browser interaction. Browser checks belong in the same
Monotools lifecycle as every other check. Success means the requested state was
proved; failure means the operator has the output and artifacts needed to act.

## Current state: 2026-08-18

The repository has a strong platform foundation and is now moving from
framework construction toward systematic extraction and product refinement.

| Vision area | Current position | Remaining work |
| --- | --- | --- |
| Central lifecycle | `manage.py` discovers, builds, validates, tests, serves, bootstraps, and runs `ui-check`. | Add planning, scaffolding, richer status, and deployment workflows as repeated app work proves their boundaries. |
| Declarative app contract | YAML metadata defines app identity, capabilities, artifacts, and routes for five apps. | Expand capability contracts without hard-coded exceptions; make lifecycle state and recovery more visible. |
| Single FastAPI service | Every discovered app exposes `/health`, declared documents, and domain routes through FastAPI. | Continue removing legacy assumptions and strengthen production startup and deployment checks. |
| Frontend system | Self-contained document and Lit artifacts build through the platform; Console Lit UI is shared by Calculator and new Lit work. | Migrate legacy pages deliberately and extract only genuinely reusable components into the catalog. |
| Persistence | SQLAlchemy repositories, SQLite data directories, migrations, constraints, provenance, and realtime models are established in several apps. | Exercise migrations more broadly and validate PostgreSQL compatibility where the domain requires it. |
| Quality infrastructure | The Python suite covers platform, HTTP, realtime, persistence, and app behavior. Playwright now verifies RPS against the real service at desktop and mobile sizes, with traces and screenshots on failure. | Add browser suites as apps mature, then introduce approved visual baselines and broader lifecycle failure tests. |
| Product proving ground | RPS is the current UI-quality proving ground, with an arena hierarchy, realtime matchmaking, durable rounds, and responsive behavior. Calculator, Quiz, Chat, and Microblog prove different platform boundaries. | Finish the RPS reveal direction, keep player ownership instantly legible, and use lessons from each app to improve shared contracts. |
| Library governance | `LIBRARIES.md` catalogs Monotools and Console Lit UI and defines extraction rules. | Keep the catalog authoritative and continue separating app domain code from shared platform code. |

## Strategic sequence

1. Make the RPS arena and reveal unmistakably readable at desktop and mobile
   sizes; treat the browser suite as a regression guard for the approved state.
2. Turn repeated app lessons into small, tested Monotools capabilities rather
   than app-specific scripts.
3. Migrate or replace legacy frontend surfaces when a shared component boundary
   is proven, preserving self-contained FastAPI-served artifacts throughout.
4. Strengthen lifecycle observability: explicit state, actionable recovery,
   deterministic artifacts, orphan-process protection, and deployment readiness.
5. Broaden browser and persistence verification only where it reduces a real
   product risk; avoid speculative framework complexity.

## What we will not become

This project is not a monolithic application that shares all domain code, a
public SDK before its contracts are proven, a collection of ad-hoc scripts, or
a frontend showcase disconnected from durable behavior. We will not trade
clarity for abstraction, or hide operational state to make the repository look
cleaner. The platform earns new generality through working applications and
evidence.

## Definition of progress

Progress is not the number of apps or commands. We are closer to the vision
when a new experiment requires less bespoke code, produces stronger evidence,
preserves more domain truth, and leaves behind a reusable improvement. The
decisive measure is compounding developer confidence: each lifecycle operation
should be easier to invoke, easier to understand, and harder to misuse than it
was in the previous experiment.
