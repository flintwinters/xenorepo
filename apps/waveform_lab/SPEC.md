# Waveform Lab specification

## Outcome

Waveform Lab lets a musician construct a 16-module subtractive synthesizer from canonical YAML,
start from a reusable instrument preset, and audition a repeating phrase without leaving the browser.

The product is an analog-style signal-flow instrument implemented with the browser Web Audio API.
It does not simulate component-level voltages, tolerances, or electrical behavior.

## Walking skeleton

FastAPI serves one self-contained Preact artifact containing two coordinated work areas:

- A CodeMirror YAML editor is the sole synth setup surface. Its named, colored instrument arrays
  each own `modules` and embedded connections, defining independent arbitrary acyclic serial and
  parallel routing. Each oscillator owns its shape and tuning.
  The audio layer derives its private single-cycle buffer; raw samples are never persisted or
  exposed. An incomplete or disconnected valid graph remains editable and silent;
  malformed or invalid drafts never replace the live setup and can be corrected or reverted.
- A piano-roll loop shows a movable four-octave window over two bars of 4/4 time at sixteenth-note
  resolution: 48 pitches by 32 steps. Its top-octave control accepts any integer whose derived pitches
  are exactly representable, so notes are not restricted to MIDI's conventional range. Multiple notes
  may occupy a step. The musician can toggle notes, adjust BPM,
  control app-level master volume, start or stop playback, and see the active step. The musician can
  export exactly one complete loop pass as a stereo 16-bit PCM WAV file. Export uses the same
  validated patch, sequencing, tempo, and master-volume signal path as live playback, renders offline
  without changing transport state, and includes bounded effect release after the final step.

The browser stores one versioned YAML document with explicit `synth` and `loop` sections after
every valid edit. CodeMirror replaces the patch-bay and waveform GUIs as the synth setup control
surface; applying a valid draft updates the live synth atomically. Notes and BPM
remain GUI-only even though the loop section is persisted as YAML. Missing, malformed, or obsolete
saved state falls back to the documented initial kit of playable `kick`, `snare`, `stick`, `bass`,
and `lead` instruments without preventing the instrument from loading, while an invalid editor draft
leaves live and saved state untouched and remains available
for correction or explicit reversion. Live audio begins only after an explicit user gesture and stops
cleanly when playback is stopped or the page is left.

## Circuit module inventory

- **Sources and control:** Oscillator, Noise, Envelope, and LFO provide tuned periodic signals,
  named noise colors, triggered shaping, and modulation.
- **Dynamics and tone:** Filter, three-band EQ, Gain, Saturation, and Compressor shape timbre and level.
- **Routing and space:** Mixer, Pan, and Output combine, position, and terminate audio paths.
- **Effects:** Delay, Chorus, Phaser, and Reverb provide bounded tails and deterministic cleanup.

Every adjustable parameter and bypass state is represented explicitly in YAML. Applying parameter
changes during playback rebuilds the graph coherently and persists without requiring transport
restart.

## Product invariants and states

- Oscillator and LFO shapes, noise colors, and filter modes use readable YAML enum names. Oscillator
  octave, semitone, and cent offsets are explicit; deterministic samples are audio-layer details.
- Circuit connections reference existing typed ports, reject self-connections and duplicates, and
  are removed with their module. Audio connections cannot originate at Output or terminate at a
  source. Modulation connections require a control source and compatible target parameter. Cycles
  are rejected before mutation. An incomplete patch remains editable and silent rather than
  failing the application.
- Each connection is stored exactly once inside its source module with explicit `from`, `to`,
  optional `type`, and optional modulation `target`; omitted type means audio. There is no separate
  top-level connection section, and the embedded `from` must match its owning module.
- Instrument names are unique and non-empty, colors are six-digit hex values, and every instrument
  owns a self-contained graph. Loop notes reference an existing instrument by name; selecting an
  instrument changes which notes the GUI edits, and assigned cells render in that instrument's color.
- Module parameters are finite and bounded by their declared ranges. Bypass preserves graph
  topology, reset restores only the selected module's defaults, and removing a module cascades only
  its attached cables.
- Modules contain only sonic identity, type, parameters, and optional bypass state; obsolete visual
  canvas coordinates are migrated away and are not part of current synth YAML. Each parameter is a
  direct module field rather than being hidden under a `parameters` wrapper.
- Omitted module parameters use registry defaults and omitted bypass means enabled. Canonical v14
  YAML rejects instrument-level `waveform`, `waveform` modules, and `adsr` modules.
- Modulation amount is optional and measured in target units; omission uses 20% of the target range.
- Root completion offers 16 complete preset instruments and chooses deterministic unique names.
- BPM is finite and bounded from 40 through 240. The sequencer has exactly 32 steps and note pitches
  may be any safely represented integer; the four-octave grid is a movable view, not a domain bound.
  App volume is finite and bounded from silence
  through unity gain, remains independent of synth Output modules, and is applied at the destination.
- Starting playback is repeatable, stopping releases scheduled voices, and graph edits rebuild the
  audio routing without accumulating browser audio nodes.
- WAV export is repeatable, operates on an immutable snapshot, encodes a standards-compliant stereo
  16-bit PCM file, and reports rendering or download failure without disrupting live playback.
- Synth YAML is validated through the domain boundary before it can replace
  live state; applying it preserves the current GUI-owned loop, and legacy JSON state migrates on
  the next valid edit.
- Keyboard users can reach the YAML controls, edit loop cells, and operate recovery actions. The
  editor suggests structural fields, module kinds, compatible parameter names, waveform and
  connection values, and existing module identifiers while typing or when completion is requested.
  Suggestions remain advisory; the domain validator remains authoritative. The
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
bounds, WAV download structure, self-contained FastAPI delivery, and the principal wide and narrow
browser journeys.

## Deferred scope

Component-level electrical simulation, user-defined module code, modulation-rate audio rendering,
polyphonic voice allocation controls, automation lanes, sample import, MIDI, live recording,
collaboration, accounts, server persistence, touch-drawing acceptance, and mobile
audio-engine claims are deferred. The analog-style modules are musically useful Web Audio models,
not claims of hardware equivalence. The circuit model stays app-owned until another monoapp proves
a generic contract.
