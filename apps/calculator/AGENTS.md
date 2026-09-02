# Project direction

## Motivation

Provide dependable ordinary arithmetic through a generated form and an authoritative stateless
server operation.
Design from the whole product, not the edited component. Model invariants, state
transitions, dependencies, adjacent journeys, degraded operation, and recovery
before implementation. Reject local correctness that creates disproportionate
global failure, surprising public behavior, or unusable control surfaces.

## Architecture

Calculator owns its FastAPI arithmetic policy and consumes generic Monotools contracts from the
enclosing Xenorepo. Its frontend is a native MonoForm artifact generated from the declared OpenAPI
operation; app-owned TypeScript and CSS are forbidden. There are no durable domain facts.
Compose established shell, pane, rail, command, and empty-state controls from `monoui`.

Inventory shared UI primitives and tokens before writing presentation code. Reuse toolkit commands
and empty states unless their semantics are demonstrably unsuitable. Treat every border, gap,
background, shadow, label, and persistent control as a visual cost that needs a functional reason;
containers are visually silent by default. Avoid slogans, serial numbers, eyebrow labels, fake
status, box-within-box composition, and other decorative AI conventions.

## Current tasks

- Keep arithmetic deterministic, finite, server-authoritative, and stateless.
- Preserve a complete OpenAPI contract that MonoForm can render without app-owned frontend code.
