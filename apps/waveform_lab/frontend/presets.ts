import type { Instrument, ModuleNode } from "./model.js";
import { registryDefaults, type ModuleKind, type ParameterValue } from "./module-registry.js";

interface Setup { readonly id: string; readonly kind: ModuleKind; readonly values?: Record<string, ParameterValue>; }
export interface PresetDefinition { readonly name: string; readonly description: string; readonly instrument: Instrument; }

const moduleOf = ({ id, kind, values }: Setup): ModuleNode => ({ id, kind,
  parameters: { ...registryDefaults(kind), ...values },
  ...(kind !== "output" && kind !== "gain" && kind !== "mixer" && kind !== "oscillator"
    && kind !== "noise" && kind !== "lfo" ? { bypass: false } : {}) });

function serial(name: string, color: string, description: string, setup: Setup[]): PresetDefinition {
  const modules = [...setup.map(moduleOf), moduleOf({ id: "output", kind: "output" })];
  const ids = modules.map((module) => module.id);
  return { name, description, instrument: { name, color, modules,
    connections: ids.slice(0, -1).map((from, index) => ({ from, to: ids[index + 1] as string })) } };
}

function graph(name: string, color: string, description: string, setup: Setup[], paths: string[][]
  ): PresetDefinition {
  const modules = [...setup.map(moduleOf), moduleOf({ id: "output", kind: "output" })];
  return { name, description, instrument: { name, color, modules,
    connections: paths.flatMap((path) => path.slice(0, -1)
      .map((from, index) => ({ from, to: path[index + 1] as string }))) } };
}

const osc = (id: string, shape: string, octave = 0, detune = 0): Setup => ({ id, kind: "oscillator",
  values: { shape, octave, detune } });
const env = (id: string, attack: number, decay: number, sustain: number, release: number): Setup =>
  ({ id, kind: "envelope", values: { attack, decay, sustain, release } });
const filter = (id: string, mode: string, frequency: number, resonance: number): Setup =>
  ({ id, kind: "filter", values: { mode, frequency, resonance } });
const gain = (id: string, value: number): Setup => ({ id, kind: "gain", values: { gain: value } });

export const PRESET_CATALOG: readonly PresetDefinition[] = [
  serial("Kick", "#fb4934", "Deep tuned electronic kick", [osc("kick-oscillator", "sine", -2),
    filter("kick-filter", "low-pass", 180, 3), env("kick-envelope", 0.001, 0.08, 0.1, 0.04),
    { id: "kick-saturation", kind: "saturation", values: { drive: 2.2, mix: 0.15 } }, gain("kick-gain", 1.1)]),
  serial("Snare", "#fe8019", "Bright filtered noise snare", [
    { id: "snare-noise", kind: "noise", values: { color: "white", level: 0.7 } },
    filter("snare-filter", "high-pass", 1200, 0.8), env("snare-envelope", 0.001, 0.1, 0.08, 0.06),
    gain("snare-gain", 0.75)]),
  serial("Clap", "#d3869b", "Short saturated noise clap", [
    { id: "clap-noise", kind: "noise", values: { color: "pink", level: 0.75 } },
    filter("clap-filter", "band-pass", 1800, 1.4), env("clap-envelope", 0.002, 0.16, 0.04, 0.09),
    { id: "clap-saturation", kind: "saturation", values: { drive: 2.5, mix: 0.2 } }, gain("clap-gain", 0.7)]),
  serial("Closed hat", "#fabd2f", "Tight high-frequency hat", [
    { id: "hat-noise", kind: "noise", values: { color: "white", level: 0.5 } },
    filter("hat-filter", "high-pass", 7000, 1.5), env("hat-envelope", 0.001, 0.025, 0, 0.015), gain("hat-gain", 0.55)]),
  serial("Open hat", "#d79921", "Longer high-frequency hat", [
    { id: "open-hat-noise", kind: "noise", values: { color: "white", level: 0.55 } },
    filter("open-hat-filter", "high-pass", 6200, 1.2), env("open-hat-envelope", 0.001, 0.12, 0.25, 0.35),
    gain("open-hat-gain", 0.5)]),
  serial("Rim/stick", "#b8bb26", "Dry rim and stick transient", [osc("stick-oscillator", "square", 1),
    filter("stick-filter", "band-pass", 4200, 5), env("stick-envelope", 0.001, 0.018, 0, 0.012),
    { id: "stick-saturation", kind: "saturation", values: { drive: 3, mix: 0.18 } }, gain("stick-gain", 0.55)]),
  serial("Tom", "#cc241d", "Tuned resonant electronic tom", [osc("tom-oscillator", "sine", -1),
    filter("tom-filter", "low-pass", 850, 4), env("tom-envelope", 0.002, 0.16, 0.12, 0.12), gain("tom-gain", 0.8)]),
  serial("Sub bass", "#83a598", "Clean octave-down sub bass", [osc("sub-oscillator", "sine", -1),
    filter("sub-filter", "low-pass", 420, 1.5), env("sub-envelope", 0.008, 0.12, 0.8, 0.2), gain("sub-gain", 0.9)]),
  serial("Acid bass", "#8ec07c", "Resonant saturated saw bass", [osc("acid-oscillator", "saw", -1),
    filter("acid-filter", "low-pass", 720, 10), env("acid-envelope", 0.005, 0.18, 0.45, 0.15),
    { id: "acid-saturation", kind: "saturation", values: { drive: 4, mix: 0.35 } }, gain("acid-gain", 0.72)]),
  serial("Pluck bass", "#458588", "Fast square bass pluck", [osc("pluck-bass-oscillator", "square", -1),
    filter("pluck-bass-filter", "low-pass", 950, 3), env("pluck-bass-envelope", 0.003, 0.14, 0.15, 0.1),
    gain("pluck-bass-gain", 0.78)]),
  graph("Saw lead", "#b8bb26", "Wide delayed saw lead", [osc("lead-a", "saw", 0, -7),
    osc("lead-b", "saw", 0, 7), { id: "lead-mixer", kind: "mixer" },
    filter("lead-filter", "low-pass", 2400, 1.8), env("lead-envelope", 0.015, 0.12, 0.78, 0.24),
    { id: "lead-pan", kind: "pan", values: { pan: 0.08 } },
    { id: "lead-delay", kind: "delay", values: { time: 0.18, feedback: 0.22, mix: 0.16 } },
    gain("lead-gain", 0.68)], [["lead-a", "lead-mixer"], ["lead-b", "lead-mixer"],
      ["lead-mixer", "lead-filter", "lead-envelope", "lead-pan", "lead-delay", "lead-gain", "output"]]),
  serial("Square lead", "#98971a", "Focused chorus square lead", [osc("square-lead-oscillator", "square"),
    filter("square-lead-filter", "low-pass", 3200, 2), env("square-lead-envelope", 0.01, 0.1, 0.72, 0.2),
    { id: "square-lead-chorus", kind: "chorus", values: { rate: 1.2, depth: 0.25, mix: 0.22 } },
    gain("square-lead-gain", 0.66)]),
  serial("Synth pluck", "#d3869b", "Echoing bright synth pluck", [osc("synth-pluck-oscillator", "triangle"),
    filter("synth-pluck-filter", "low-pass", 2800, 3), env("synth-pluck-envelope", 0.002, 0.12, 0.08, 0.14),
    { id: "synth-pluck-delay", kind: "delay", values: { time: 0.22, feedback: 0.28, mix: 0.24 } },
    gain("synth-pluck-gain", 0.72)]),
  graph("Organ", "#689d6a", "Parallel drawbar-like oscillators", [osc("organ-root", "sine"),
    osc("organ-octave", "sine", 1), osc("organ-fifth", "sine", 0), { id: "organ-mixer", kind: "mixer" },
    env("organ-envelope", 0.02, 0.05, 0.92, 0.18), gain("organ-gain", 0.58)],
    [["organ-root", "organ-mixer"], ["organ-octave", "organ-mixer"], ["organ-fifth", "organ-mixer"],
      ["organ-mixer", "organ-envelope", "organ-gain", "output"]]),
  graph("Warm pad", "#b16286", "Slow detuned chorus and reverb pad", [osc("pad-a", "saw", 0, -10),
    osc("pad-b", "saw", 0, 10), { id: "pad-mixer", kind: "mixer" },
    filter("pad-filter", "low-pass", 1800, 1.2), env("pad-envelope", 0.8, 0.5, 0.8, 2.5),
    { id: "pad-chorus", kind: "chorus", values: { rate: 0.45, depth: 0.5, mix: 0.42 } },
    { id: "pad-reverb", kind: "reverb", values: { decay: 3.5, mix: 0.38 } }, gain("pad-gain", 0.52)],
    [["pad-a", "pad-mixer"], ["pad-b", "pad-mixer"],
      ["pad-mixer", "pad-filter", "pad-envelope", "pad-chorus", "pad-reverb", "pad-gain", "output"]]),
  graph("Noise riser", "#928374", "LFO-swept atmospheric noise", [
    { id: "riser-noise", kind: "noise", values: { color: "pink", level: 0.45 } },
    filter("riser-filter", "band-pass", 900, 4), env("riser-envelope", 1.2, 0.4, 0.85, 1.5),
    { id: "riser-lfo", kind: "lfo", values: { shape: "saw", rate: 0.18, depth: 0.8 } },
    { id: "riser-pan", kind: "pan", values: { pan: 0 } },
    { id: "riser-reverb", kind: "reverb", values: { decay: 4, mix: 0.45 } }, gain("riser-gain", 0.5)],
    [["riser-noise", "riser-filter", "riser-envelope", "riser-pan", "riser-reverb", "riser-gain", "output"]]),
] as const;

export function presetInstrument(name: string, instrumentName = name): Instrument {
  const preset = PRESET_CATALOG.find((item) => item.name === name);
  if (!preset) throw new Error(`Unknown preset: ${name}`);
  return structuredClone({ ...preset.instrument, name: instrumentName });
}

export function freshInstruments(): Instrument[] {
  return [["Kick", "kick"], ["Snare", "snare"], ["Rim/stick", "stick"], ["Sub bass", "bass"],
    ["Saw lead", "lead"]].map(([preset, name]) => presetInstrument(preset as string, name));
}
