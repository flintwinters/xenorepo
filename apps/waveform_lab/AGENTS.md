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

- The four-octave grid navigates an unbounded integer pitch domain without constraining stored notes.
- YAML completion derives module and parameter suggestions from the domain inventory.
- Fresh and prior-default recovery provides a five-voice percussion, bass, and lead starter kit.
- Shared command controls and semantic piano-grid styling pass wide/narrow acceptance.
- Next: profile larger polyphonic graphs before introducing shared effect buses or AudioWorklets.
