import { parse, stringify } from "yaml";
import { STATE_VERSION, validatedState, type Instrument, type LabState, type ModuleNode } from "./model.js";

interface SynthState { instruments: object[]; }

function moduleOf(module: ModuleNode, instrument: Instrument): object {
  const connections = instrument.connections.filter((edge) => edge.from === module.id);
  return { id: module.id, kind: module.kind, ...module.parameters,
    ...(module.bypass === undefined ? {} : { bypass: module.bypass }),
    ...(connections.length ? { connections } : {}) };
}

function synthOf(state: LabState): SynthState {
  return { instruments: state.instruments.map((instrument) => ({
    name: instrument.name, color: instrument.color, waveform: instrument.waveform,
    modules: instrument.modules.map((module) => moduleOf(module, instrument)),
  })) };
}

function documentOf(state: LabState): object {
  return {
    version: STATE_VERSION,
    synth: synthOf(state),
    loop: { bpm: state.bpm, volume: state.volume, notes: state.notes },
  };
}

export function encodeState(state: LabState): string { return stringify(documentOf(state), { lineWidth: 0 }); }

export function decodeState(source: string): LabState | null {
  try { return validatedState(parse(source)); } catch { return null; }
}

export function encodeSynth(state: LabState): string {
  return stringify({ synth: synthOf(state) }, { lineWidth: 0 });
}

export function applySynth(source: string, current: LabState): LabState {
  let parsed: unknown;
  try { parsed = parse(source); } catch (error) {
    throw new Error(error instanceof Error ? error.message : "YAML could not be parsed.");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed) || !("synth" in parsed))
    throw new Error("The document must contain a synth mapping.");
  const candidate = validatedState({
    version: STATE_VERSION,
    synth: (parsed as { synth: unknown }).synth,
    loop: { bpm: current.bpm, volume: current.volume, notes: current.notes },
  });
  if (!candidate) throw new Error("Synth YAML violates the module, connection, or waveform contract.");
  return candidate;
}
