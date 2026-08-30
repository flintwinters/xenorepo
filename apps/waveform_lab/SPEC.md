# Waveform Lab specification

## Outcome

Waveform Lab lets a musician construct a small modular synthesizer, shape its oscillator waveform
precisely, and audition a repeating phrase without leaving the browser. The first release succeeds
when the musician can draw a valid single-cycle waveform, patch a playable signal path, enter a
two-bar melody, hear the loop at an adjustable tempo, and return later to the same patch.

The product is an analog-style signal-flow instrument implemented with the browser Web Audio API.
It does not simulate component-level voltages, tolerances, or electrical behavior.

## Walking skeleton

FastAPI serves one self-contained Preact artifact containing two coordinated work areas:

- A CodeMirror YAML editor is the sole synth setup surface. Its `modules`, `connections`, and named
  `waveform` fields define arbitrary acyclic serial and parallel routing and the oscillator shape.
  The audio layer derives its private single-cycle buffer; raw samples are never persisted or
  exposed. An incomplete or disconnected valid graph remains editable and silent;
  malformed or invalid drafts never replace the live setup and can be corrected or reverted.
- A piano-roll loop spans C3 through B6 over two bars of 4/4 time at sixteenth-note resolution: 48
  pitches by 32 steps. Multiple notes may occupy a step. The musician can toggle notes, adjust BPM,
  control app-level master volume, start or stop playback, and see the active step.

The browser stores one versioned YAML document with explicit `synth` and `loop` sections after
every valid edit. CodeMirror replaces the patch-bay and waveform GUIs as the synth setup control
surface; applying a valid draft updates the live synth atomically. Notes and BPM
remain GUI-only even though the loop section is persisted as YAML. Missing, malformed, or obsolete
saved state falls back to the documented initial patch without preventing the instrument from
loading, while an invalid editor draft leaves live and saved state untouched and remains available
for correction or explicit reversion. Audio begins only after an explicit user gesture and stops
cleanly when playback is stopped or the page is left.

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

Every adjustable parameter and bypass state is represented explicitly in YAML. Applying parameter
changes during playback rebuilds the graph coherently and persists without requiring transport
restart.

## Product invariants and states

- Waveform is one of `sine`, `square`, `saw`, or `triangle`; deterministic finite normalized samples
  are derived only inside the audio layer.
- Circuit connections reference existing typed ports, reject self-connections and duplicates, and
  are removed with their module. Audio connections cannot originate at Output or terminate at a
  source. Modulation connections require a control source and compatible target parameter. Cycles
  are rejected before mutation. An incomplete patch remains editable and silent rather than
  failing the application.
- Each connection is stored exactly once inside its source module with explicit `from`, `to`,
  `type`, and optional modulation `target`; there is no separate top-level connection section, and
  the embedded `from` must match its owning module.
- Module parameters are finite and bounded by their declared ranges. Bypass preserves graph
  topology, reset restores only the selected module's defaults, and removing a module cascades only
  its attached cables.
- Modules contain only sonic identity, type, parameters, and optional bypass state; obsolete visual
  canvas coordinates are migrated away and are not part of current synth YAML. Each parameter is a
  direct module field rather than being hidden under a `parameters` wrapper.
- BPM is finite and bounded from 40 through 240. The sequencer has exactly 32 steps and its note
  pitches remain inside the declared four-octave range. App volume is finite and bounded from silence
  through unity gain, remains independent of synth Output modules, and is applied at the destination.
- Starting playback is repeatable, stopping releases scheduled voices, and graph edits rebuild the
  audio routing without accumulating browser audio nodes.
- Synth YAML is validated through the domain boundary before it can replace
  live state; applying it preserves the current GUI-owned loop, and legacy JSON state migrates on
  the next valid edit.
- Keyboard users can reach the YAML controls, edit loop cells, and operate recovery actions. The
  document and loop remain fully fitted without scrollbars at wide and narrow viewports; only the
  code editor owns overflow and scrolling.

## Real-world validation

In a desktop Chromium session, retain the initial playable patch and use YAML to build a parallel
branch with Noise, Filter, Saturation, Chorus, Delay, Reverb, Compressor, and Mixer. Configure
module parameters, bypass state, LFO and ADSR modulation, and a named waveform. Attempt malformed,
out-of-range, duplicate, and cyclic setup documents and confirm they are rejected without damaging
the patch. Enter
notes at the first and last steps across both octaves, change BPM during playback, and observe the
playhead cross the two-bar boundary. Reload and confirm the graph, controls, waveform, notes, and
tempo survive. Remove a routed module and confirm only its cables disappear. Complete the control
journey by keyboard at a narrow viewport.

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
