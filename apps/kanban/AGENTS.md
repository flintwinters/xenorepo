# Project direction

## Motivation

Give one person a calm, durable, recoverable board for turning unordered work into visible progress.

## Architecture

Kanban owns its product behavior and consumes generic Monotools contracts from the enclosing
Xenorepo. Keep frontend, backend, tests, and durable domain facts app-owned.

Inventory shared UI primitives and tokens before writing presentation code. Reuse toolkit commands
and empty states unless their semantics are demonstrably unsuitable. Treat every border, gap,
background, shadow, label, and persistent control as a visual cost that needs a functional reason;
containers are visually silent by default. Avoid slogans, serial numbers, eyebrow labels, fake
status, box-within-box composition, and other decorative AI conventions.

## Current tasks

- Implement and prove the decision-complete walking skeleton in `SPEC.md`.
- Inspect populated wide and narrow screenshots and explicitly critique AI artifacts, control
  clutter, hierarchy loss, and responsive structure before declaring the UI complete.
