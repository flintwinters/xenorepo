# Waveform Lab

[Xenorepo on GitHub](https://github.com/flintwinters/xenorepo)

Waveform Lab is a browser-based modular synthesizer centered on a precise single-cycle waveform
definition, typed modular routing, and a two-bar piano roll. Its thirteen audio and control
modules include waveform and noise sources, ADSR and LFO modulation, filtering, saturation,
compression, delay, chorus, convolution reverb, mixing, gain, and output. FastAPI serves the
self-contained Preact interface; Web Audio and browser-local YAML storage provide sound and
versioned patch persistence without a second runtime service. A CodeMirror YAML surface is the only
synth setup editor and applies changes atomically. Named, colored instruments own independent module
graphs; the GUI-only loop selects an instrument and renders its assigned notes in that color.

Use the Xenorepo cockpit for every lifecycle operation:

```console
uv run manage.py waveform_lab check
uv run manage.py waveform_lab test
uv run manage.py waveform_lab ui-check
uv run manage.py waveform_lab serve
```

The app deliberately consumes the enclosing Xenorepo's Monotools version. A future explicit
standalone-export contract may pin that dependency without changing the app's Git history.
