# Waveform Lab specification

## Outcome

Waveform Lab lets a musician construct a small modular synthesizer, shape its oscillator waveform
precisely, and audition a repeating phrase without leaving the browser. The first release succeeds
when the musician can draw a valid single-cycle waveform, patch a playable signal path, enter a
two-bar melody, hear the loop at an adjustable tempo, and return later to the same patch.

The product is an analog-style signal-flow instrument implemented with the browser Web Audio API.
It does not simulate component-level voltages, tolerances, or electrical behavior.

## Walking skeleton

FastAPI serves one self-contained Preact artifact containing three coordinated work areas:

- A freeform circuit canvas can add, move, connect, disconnect, and remove Waveform, Gain, and
  Output modules. Typed audio ports permit only meaningful output-to-input connections. A complete
  Waveform-to-Gain-to-Output path is the initial patch, while editing operations remain available
  during playback.
- The Waveform module opens a strong single-cycle editor. Pointer drawing produces one normalized
  amplitude for every horizontal sample position, preserving a vertical-line-test-passing function
  that can be resampled deterministically into a Web Audio periodic wave. Sine, square, saw, and
  triangle presets, undo, and reset make exploration recoverable.
- A piano-roll loop spans C4 through B5 over two bars of 4/4 time at sixteenth-note resolution: 24
  pitches by 32 steps. Multiple notes may occupy a step. The musician can toggle notes, adjust BPM,
  start or stop playback, and see the active step.

The browser stores the circuit, waveform, notes, and BPM locally after every valid edit. Missing,
malformed, or obsolete saved state falls back to the documented initial patch without preventing
the instrument from loading. Audio begins only after an explicit user gesture and stops cleanly
when playback is stopped or the page is left.

## Product invariants and states

- Waveform samples are finite normalized values in `[-1, 1]`; drawing interpolates across skipped
  pointer positions and never creates multiple amplitudes for one horizontal position.
- Circuit connections reference existing typed ports, reject self-connections and duplicates, and
  are removed with their module. An incomplete patch remains editable and silent rather than
  failing the application.
- BPM is finite and bounded from 40 through 240. The sequencer has exactly 32 steps and its note
  pitches remain inside the declared two-octave range.
- Starting playback is repeatable, stopping releases scheduled voices, and graph edits rebuild the
  audio routing without accumulating browser audio nodes.
- Keyboard users can reach controls, edit loop cells, and operate waveform presets and recovery
  actions. The layout remains usable at a narrow viewport; precision pointer drawing is a desktop
  acceptance claim, not a touch claim.

## Real-world validation

In a desktop Chromium session, add and reposition modules, replace connections to produce a valid
Waveform-to-Gain-to-Output patch, choose a preset, draw a visibly different waveform, and undo the
drawing. Enter notes at the first and last steps across both octaves, set a non-default BPM, start
playback, and observe the playhead cross the two-bar boundary. Reload and confirm that the circuit,
waveform, notes, and tempo survive. Remove a required connection and confirm playback becomes silent
while editing remains available, then reconnect it and recover sound. Complete the same control
journey by keyboard at a narrow viewport, excluding freehand drawing.

Automated acceptance proves deterministic waveform normalization and interpolation, circuit graph
validation and cascading removal, saved-state validation and recovery, sequencer dimensions and BPM
bounds, self-contained FastAPI delivery, and the principal wide and narrow browser journeys.

## Deferred scope

Additional module types, component-level analog simulation, modulation and control-voltage ports,
polyphonic voice controls, envelopes, filters, effects, automation lanes, sample import, MIDI,
recording, audio export, collaboration, accounts, server persistence, touch-drawing acceptance, and
mobile audio-engine claims are deferred. The circuit model stays app-owned until another monoapp
proves a generic contract.
