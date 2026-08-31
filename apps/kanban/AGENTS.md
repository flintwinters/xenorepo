# Project direction

## Motivation

Give one person a fast, durable view of work moving through a process. Prefer
clear workflow state, deterministic ordering, and loss-resistant mutations over
collaboration breadth.

## Architecture

Kanban Board owns its product behavior and consumes generic Monotools contracts from the enclosing
Xenorepo. Keep frontend, backend, tests, and durable domain facts app-owned.

## Current tasks

- The specified single-board walking skeleton is implemented with durable
  configurable columns, ordered cards, and wide/narrow acceptance evidence.
- Run the real-world pilot in `SPEC.md`; promote only after its actual workflow
  and restart observations agree with the automated acceptance contract.
