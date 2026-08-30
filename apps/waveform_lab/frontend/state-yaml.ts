import { parse, stringify } from "yaml";
import { STATE_VERSION, validatedState, type LabState, type ModuleNode } from "./model.js";

interface SynthState { modules: object[]; connections: LabState["connections"]; waveform: LabState["waveform"]; }

function moduleOf(module: ModuleNode): object {
  return { id: module.id, kind: module.kind, ...module.parameters,
    ...(module.bypass === undefined ? {} : { bypass: module.bypass }) };
}

function synthOf(state: LabState): SynthState {
  return { modules: state.modules.map(moduleOf), connections: state.connections, waveform: state.waveform };
}

function documentOf(state: LabState): object {
  return {
    version: STATE_VERSION,
    synth: synthOf(state),
    loop: { bpm: state.bpm, volume: state.volume, notes: state.notes, holds: state.holds },
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
    loop: { bpm: current.bpm, volume: current.volume, notes: current.notes, holds: current.holds },
  });
  if (!candidate) throw new Error("Synth YAML violates the module, connection, or waveform contract.");
  return candidate;
}
