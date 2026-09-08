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

- Keep the shipped single-board walking skeleton and its recoverable archive semantics aligned with
  `SPEC.md`.
- Preserve the deterministic populated wide/narrow baselines and the horizontal workflow structure
  on small screens.
- Keep copy and atomic append/replace import aligned as one explicit, flat current-state contract.
- Keep each card's visible timestamped log derived from the immutable activity stream, including
  activity for its comments and attachments; do not create a competing history authority.
- Keep workflow state singular: columns communicate where work stands, with no parallel card
  priority field or tag.
