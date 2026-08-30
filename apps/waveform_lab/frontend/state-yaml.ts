import { parse, stringify } from "yaml";
import { STATE_VERSION, defaultParameters, validatedState,
  type Connection, type Instrument, type LabState, type ModuleNode } from "./model.js";

function moduleOf(module: ModuleNode, instrument: Instrument): object {
  const defaults = defaultParameters(module.kind);
  const parameters = Object.fromEntries(Object.entries(module.parameters ?? {})
    .filter(([name, value]) => value !== defaults[name]));
  const connections = instrument.connections.filter((edge) => edge.from === module.id).map(connectionOf);
  return { id: module.id, kind: module.kind, ...parameters,
    ...(module.bypass ? { bypass: true } : {}),
    ...(connections.length ? { connections } : {}) };
}

function connectionOf(connection: Connection): object {
  return { from: connection.from, to: connection.to,
    ...((connection.type ?? "audio") === "audio" ? {} : { type: connection.type }),
    ...(connection.target === undefined ? {} : { target: connection.target }) };
}

function instrumentMapOf(state: LabState): Record<string, object> {
  return Object.fromEntries(state.instruments.map((instrument) => [instrument.name, {
    color: instrument.color,
    ...(instrument.waveform === "sine" ? {} : { waveform: instrument.waveform }),
    modules: instrument.modules.map((module) => moduleOf(module, instrument)),
  }]));
}

function documentOf(state: LabState): object {
  return {
    version: STATE_VERSION,
    ...instrumentMapOf(state),
    loop: { bpm: state.bpm, volume: state.volume, notes: state.notes },
  };
}

export function encodeState(state: LabState): string { return stringify(documentOf(state), { lineWidth: 0 }); }

export function decodeState(source: string): LabState | null {
  try { return validatedState(parse(source)); } catch { return null; }
}

export function encodeSynth(state: LabState): string {
  return stringify(instrumentMapOf(state), { lineWidth: 0 });
}

export function applySynth(source: string, current: LabState): LabState {
  let parsed: unknown;
  try { parsed = parse(source); } catch (error) {
    throw new Error(error instanceof Error ? error.message : "YAML could not be parsed.");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
    throw new Error("The document must map instrument names to their setup.");
  if ("version" in parsed || "loop" in parsed)
    throw new Error("Instrument names cannot be 'version' or 'loop'.");
  const candidate = validatedState({
    version: STATE_VERSION,
    ...parsed,
    loop: { bpm: current.bpm, volume: current.volume, notes: current.notes },
  });
  if (!candidate) throw new Error("Synth YAML violates the module, connection, or waveform contract.");
  return candidate;
}
