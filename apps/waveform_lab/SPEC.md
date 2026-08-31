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

- A freeform circuit canvas can add, move, connect, disconnect, bypass, reset, and remove modules.
  Typed audio and modulation ports permit arbitrary acyclic serial and parallel routing. A Mixer
  combines branches; an incomplete or disconnected graph remains editable and silent.
- The Waveform module opens a strong single-cycle editor. Pointer drawing produces one normalized
  amplitude for every horizontal sample position, preserving a vertical-line-test-passing function
  that can be resampled deterministically into a Web Audio periodic wave. Sine, square, saw, and
  triangle presets, undo, and reset make exploration recoverable.
- A piano-roll loop spans C4 through B5 over two bars of 4/4 time at sixteenth-note resolution: 24
  pitches by 32 steps. Multiple notes may occupy a step, and a note can be held through subsequent
  steps without being retriggered. The musician can toggle notes and holds, adjust BPM, start or
  stop playback, and see the active step.

The browser stores the circuit, waveform, notes, and BPM locally after every valid edit. Missing,
malformed, or obsolete saved state falls back to the documented initial patch without preventing
the instrument from loading. Audio begins only after an explicit user gesture and stops cleanly
when playback is stopped or the page is left.

## Circuit module inventory

- **Sources:** Waveform emits the user-drawn periodic signal for sequenced pitches; Noise emits a
  bounded noise signal. Neither accepts an audio input.
- **Dynamics and tone:** Gain controls level; ADSR shapes triggered notes; Filter provides
  low-pass, high-pass, band-pass, and notch modes; Compressor bounds dynamics; Saturation applies
  a continuously variable nonlinear waveshaping curve.
- **Time and space:** Delay controls time, feedback, and wet mix; Chorus controls rate, depth, and
  wet mix; Reverb controls decay and wet mix through a deterministic generated impulse response.
- **Routing and control:** Mixer combines audio branches; Output connects the final signal to the
  browser destination. LFO and ADSR expose typed modulation outputs to compatible Gain, Filter,
  Saturation, Delay, Reverb, Chorus, and Compressor parameters.

Every adjustable parameter is visible directly on its expanded module. Effects expose bypass and
reset controls. Parameter changes made during playback rebuild or update the graph coherently and
persist without requiring transport restart.

## Product invariants and states

- Waveform samples are finite normalized values in `[-1, 1]`; drawing interpolates across skipped
  pointer positions and never creates multiple amplitudes for one horizontal position.
- Circuit connections reference existing typed ports, reject self-connections and duplicates, and
  are removed with their module. Audio connections cannot originate at Output or terminate at a
  source. Modulation connections require a control source and compatible target parameter. Cycles
  are rejected before mutation. An incomplete patch remains editable and silent rather than
  failing the application.
- Module parameters are finite and bounded by their declared ranges. Bypass preserves graph
  topology, reset restores only the selected module's defaults, and removing a module cascades only
  its attached cables.
- BPM is finite and bounded from 40 through 240. The sequencer has exactly 32 steps and its note
  pitches remain inside the declared two-octave range. Every held cell continues an onset or prior
  held cell of the same pitch; removing an onset removes its contiguous holds.
- Starting playback is repeatable, stopping releases scheduled voices, and graph edits rebuild the
  audio routing without accumulating browser audio nodes.
- Keyboard users can reach controls, edit loop cells, and operate waveform presets and recovery
  actions. The layout remains usable at a narrow viewport; precision pointer drawing is a desktop
  acceptance claim, not a touch claim.

## Real-world validation

In a desktop Chromium session, retain the initial playable patch and build a parallel branch using
Noise, Filter, Saturation, Chorus, Delay, Reverb, Compressor, and Mixer. Adjust every module, bypass
and reset an effect, and connect LFO and ADSR modulation to compatible parameters. Attempt invalid
audio, modulation, duplicate, and cyclic cables and confirm they are rejected without damaging the
patch. Choose a waveform preset, draw a visibly different waveform, and undo the drawing. Enter
notes at the first and last steps across both octaves, change BPM during playback, and observe the
playhead cross the two-bar boundary. Reload and confirm the graph, controls, waveform, notes, and
tempo survive. Remove a routed module and confirm only its cables disappear. Complete the control
journey by keyboard at a narrow viewport, excluding freehand drawing.

Automated acceptance proves deterministic waveform normalization and interpolation, circuit graph
validation and cascading removal, saved-state validation and recovery, sequencer dimensions and BPM
bounds, self-contained FastAPI delivery, and the principal wide and narrow browser journeys.

## Deferred scope

Component-level electrical simulation, user-defined module code, modulation-rate audio rendering,
polyphonic voice allocation controls, automation lanes, sample import, MIDI, recording, audio
export, collaboration, accounts, server persistence, touch-drawing acceptance, and mobile
audio-engine claims are deferred. The analog-style modules are musically useful Web Audio models,
not claims of hardware equivalence. The circuit model stays app-owned until another monoapp proves
a generic contract.
