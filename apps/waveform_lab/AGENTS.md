# Project direction

## Motivation

Let a musician construct, shape, sequence, hear, and recover a compact modular synthesizer patch.
Design from the whole product, not the edited component. Model invariants, state
transitions, dependencies, adjacent journeys, degraded operation, and recovery
before implementation. Reject local correctness that creates disproportionate
global failure, surprising public behavior, or unusable control surfaces.

## Architecture

Waveform Lab owns its product behavior and consumes generic Monotools contracts from the enclosing
Xenorepo. Keep frontend, backend, tests, and durable domain facts app-owned.

## Current tasks

- Implicit reserved outputs and lossless explicit-output migration pass wide/narrow acceptance.
- Next: profile larger polyphonic graphs before introducing shared effect buses or AudioWorklets.
