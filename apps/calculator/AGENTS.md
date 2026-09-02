# Project direction

## Motivation

Provide dependable ordinary arithmetic through a small, button-only interface that keeps no user
data.
Design from the whole product, not the edited component. Model invariants, state
transitions, dependencies, adjacent journeys, degraded operation, and recovery
before implementation. Reject local correctness that creates disproportionate
global failure, surprising public behavior, or unusable control surfaces.

## Architecture

Calculator owns its Preact arithmetic state machine and consumes generic Monotools contracts from
the enclosing Xenorepo. FastAPI only serves the compiled artifact; there are no durable domain facts.
Compose established shell, pane, rail, command, and empty-state controls from `@xenorepo/ui`.

Inventory shared UI primitives and tokens before writing presentation code. Reuse toolkit commands
and empty states unless their semantics are demonstrably unsuitable. Treat every border, gap,
background, shadow, label, and persistent control as a visual cost that needs a functional reason;
containers are visually silent by default. Avoid slogans, serial numbers, eyebrow labels, fake
status, box-within-box composition, and other decorative AI conventions.

## Current tasks

- Keep arithmetic behavior deterministic and stateless while preserving button-only input.
- Preserve complete, uncluttered wide and narrow calculator layouts.
