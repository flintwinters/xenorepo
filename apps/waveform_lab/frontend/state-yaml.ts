import { parse, stringify } from "yaml";
import { STATE_VERSION, validatedState, type LabState } from "./model.js";

export type SynthState = Pick<LabState, "modules" | "connections" | "samples">;

function synthOf(state: LabState): SynthState {
  return { modules: state.modules, connections: state.connections, samples: state.samples };
}

function documentOf(state: LabState): object {
  return {
    version: STATE_VERSION,
    synth: synthOf(state),
    loop: { bpm: state.bpm, notes: state.notes, holds: state.holds },
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
    loop: { bpm: current.bpm, notes: current.notes, holds: current.holds },
  });
  if (!candidate) throw new Error("Synth YAML violates the module, connection, or waveform contract.");
  return candidate;
}
