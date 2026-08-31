# Project direction

## Motivation

Give one person a fast, durable view of work moving through a process. Prefer
clear workflow state, deterministic ordering, and loss-resistant mutations over
collaboration breadth.

## Architecture

Kanban Board owns its product behavior and consumes generic Monotools contracts from the enclosing
Xenorepo. Keep frontend, backend, tests, and durable domain facts app-owned.

## Current tasks

- Implement the specified single-board column and card lifecycle as a shippable
  walking skeleton.
- Prove exact ordering, restart persistence, and trusted drag behavior through
  the app-owned acceptance journey.
