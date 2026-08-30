const SAMPLE_COUNT = 128;
export const STEP_COUNT = 32;
export const STATE_VERSION = 11 as const;
export const PITCHES = Array.from({ length: 48 }, (_, index) => 95 - index);
export type WaveformShape = "sine" | "square" | "saw" | "triangle";

export type ModuleKind = "waveform" | "gain" | "output" | "filter" | "adsr" | "saturation"
  | "delay" | "reverb" | "mixer" | "chorus" | "compressor" | "noise" | "lfo";
export type ConnectionType = "audio" | "modulation";
export type ModuleParameters = Record<string, number>;
export interface ModuleNode {
  id: string; kind: ModuleKind;
  parameters?: ModuleParameters; bypass?: boolean;
}
/** Optional for source compatibility with the v1 UI; absent means audio. */
export interface Connection {
  from: string; to: string; type?: ConnectionType; target?: string;
}
export interface Instrument {
  name: string; color: string; waveform: WaveformShape;
  modules: ModuleNode[]; connections: Connection[];
}
export interface SequencedNote { pitch: number; instrument: string; }
export interface LabState {
  version: typeof STATE_VERSION; instruments: Instrument[];
  notes: SequencedNote[][]; bpm: number; volume: number;
}

type Bounds = Readonly<Record<string, readonly [number, number]>>;
export const PARAMETER_BOUNDS: Readonly<Record<ModuleKind, Bounds>> = {
  waveform: { detune: [-1200, 1200] }, gain: { gain: [0, 2] }, output: { level: [0, 1] },
  filter: { mode: [0, 3], frequency: [20, 20000], resonance: [0.1, 30] },
  adsr: { attack: [0.001, 10], decay: [0.001, 10], sustain: [0, 1], release: [0.001, 20] },
  saturation: { drive: [1, 20], mix: [0, 1] },
  delay: { time: [0, 2], feedback: [0, 0.95], mix: [0, 1] },
  reverb: { decay: [0.1, 20], mix: [0, 1] }, mixer: { level: [0, 2] },
  chorus: { rate: [0.05, 10], depth: [0, 1], mix: [0, 1] },
  compressor: { threshold: [-100, 0], ratio: [1, 20], attack: [0, 1], release: [0, 1] },
  noise: { color: [0, 2], level: [0, 1] }, lfo: { shape: [0, 3], rate: [0.01, 30], depth: [0, 1] },
};
export const MODULATION_TARGETS: Readonly<Partial<Record<ModuleKind, readonly string[]>>> = {
  waveform: ["detune"], gain: ["gain"], output: ["level"], filter: ["frequency", "resonance"],
  saturation: ["drive", "mix"], delay: ["time", "feedback", "mix"], reverb: ["mix"],
  mixer: ["level"], chorus: ["rate", "depth", "mix"],
  compressor: ["threshold", "ratio", "attack", "release"], noise: ["level"],
};
const defaults: Readonly<Record<ModuleKind, ModuleParameters>> = {
  waveform: { detune: 0 }, gain: { gain: 0.8 }, output: { level: 0.8 },
  filter: { mode: 0, frequency: 1200, resonance: 1 },
  adsr: { attack: 0.01, decay: 0.15, sustain: 0.7, release: 0.3 },
  saturation: { drive: 2, mix: 0.5 }, delay: { time: 0.25, feedback: 0.3, mix: 0.25 },
  reverb: { decay: 2, mix: 0.25 }, mixer: { level: 1 },
  chorus: { rate: 1.5, depth: 0.35, mix: 0.3 },
  compressor: { threshold: -24, ratio: 4, attack: 0.01, release: 0.25 },
  noise: { color: 0, level: 0.25 }, lfo: { shape: 0, rate: 2, depth: 0.5 },
};
const kinds = new Set<ModuleKind>(Object.keys(PARAMETER_BOUNDS) as ModuleKind[]);
const sources = new Set<ModuleKind>(["waveform", "noise"]);
const controls = new Set<ModuleKind>(["adsr", "lfo"]);
const bypassable = new Set<ModuleKind>(["filter", "adsr", "saturation", "delay", "reverb", "chorus", "compressor"]);

export function defaultParameters(kind: ModuleKind): ModuleParameters { return { ...defaults[kind] }; }
export function createModule(id: string, kind: ModuleKind): ModuleNode {
  return { id, kind, parameters: defaultParameters(kind), ...(bypassable.has(kind) ? { bypass: false } : {}) };
}

export function waveformSamples(kind: WaveformShape): number[] {
  return Array.from({ length: SAMPLE_COUNT }, (_, index) => {
    const phase = index / SAMPLE_COUNT;
    if (kind === "sine") return Math.sin(phase * Math.PI * 2);
    if (kind === "square") return phase < 0.5 ? 1 : -1;
    if (kind === "saw") return 1 - phase * 2;
    return 1 - 4 * Math.abs(phase - 0.5);
  });
}

export function initialState(): LabState {
  return {
    version: STATE_VERSION,
    instruments: [{ name: "main", color: "#b8bb26", waveform: "sine",
      modules: [createModule("waveform-1", "waveform"), createModule("gain-1", "gain"),
        createModule("output", "output")],
      connections: [{ from: "waveform-1", to: "gain-1", type: "audio" },
        { from: "gain-1", to: "output", type: "audio" }] }],
    notes: Array.from({ length: STEP_COUNT }, () => []), bpm: 120, volume: 0.8,
  };
}

function finite(value: unknown): value is number { return typeof value === "number" && Number.isFinite(value); }
function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
function validParameters(kind: ModuleKind, value: unknown): value is ModuleParameters {
  if (!record(value)) return false;
  const bounds = PARAMETER_BOUNDS[kind];
  const names = Object.keys(bounds);
  return Object.keys(value).length === names.length && names.every((name) => {
    const range = bounds[name];
    if (!range) return false;
    return finite(value[name]) && value[name] >= range[0] && value[name] <= range[1];
  });
}
type StateVersion = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | typeof STATE_VERSION;
function flatParameters(kind: ModuleKind, value: Record<string, unknown>, requireAll: boolean
    ): ModuleParameters | null {
  const parameters = defaultParameters(kind);
  for (const [name, range] of Object.entries(PARAMETER_BOUNDS[kind])) {
    if (value[name] === undefined) { if (requireAll) return null; continue; }
    if (!finite(value[name]) || value[name] < range[0] || value[name] > range[1]) return null;
    parameters[name] = value[name];
  }
  return parameters;
}
function validModule(value: unknown, version: StateVersion): value is ModuleNode {
  if (!record(value) || typeof value.id !== "string" || !value.id || !kinds.has(value.kind as ModuleKind)) return false;
  const kind = value.kind as ModuleKind;
  if (version === 1) return finite(value.x) && finite(value.y) && ["waveform", "gain", "output"].includes(kind);
  if (version === 2 && (!finite(value.x) || !finite(value.y))) return false;
  if (version >= 3 && version <= 5) {
    const expected = new Set(["id", "kind", "parameters", ...(bypassable.has(kind) ? ["bypass"] : [])]);
    if (Object.keys(value).some((name) => !expected.has(name))) return false;
  }
  if (version >= 6) {
    const expected = new Set(["id", "kind", ...Object.keys(PARAMETER_BOUNDS[kind]),
      ...(bypassable.has(kind) ? ["bypass"] : []), ...(version >= 7 ? ["connections"] : [])]);
    if (Object.keys(value).some((name) => !expected.has(name))
      || !flatParameters(kind, value, version < 9)) return false;
    if (version >= 7 && value.connections !== undefined && !Array.isArray(value.connections)) return false;
  } else if (!validParameters(kind, value.parameters)) return false;
  return bypassable.has(kind) ? (version >= 9 ? value.bypass === undefined
    || typeof value.bypass === "boolean" : typeof value.bypass === "boolean") : value.bypass === undefined;
}
function edgeType(edge: Connection): ConnectionType { return edge.type ?? "audio"; }
export function acceptsAudio(kind: ModuleKind): boolean { return !sources.has(kind) && kind !== "lfo"; }
export function emitsAudio(kind: ModuleKind): boolean { return kind !== "output" && kind !== "lfo"; }
export function emitsControl(kind: ModuleKind): boolean { return controls.has(kind); }
function createsCycle(connections: Connection[], candidate: Connection): boolean {
  const adjacency = new Map<string, string[]>();
  for (const edge of [...connections, candidate]) {
    const next = adjacency.get(edge.from) ?? []; next.push(edge.to); adjacency.set(edge.from, next);
  }
  const pending = [candidate.to];
  const visited = new Set<string>();
  while (pending.length) {
    const id = pending.pop() as string;
    if (id === candidate.from) return true;
    if (!visited.has(id)) { visited.add(id); pending.push(...(adjacency.get(id) ?? [])); }
  }
  return false;
}

export function validConnection(modules: ModuleNode[], edge: Connection, existing: Connection[] = []): boolean {
  const from = modules.find((node) => node.id === edge.from);
  const to = modules.find((node) => node.id === edge.to);
  if (!from || !to || from.id === to.id || createsCycle(existing, edge)) return false;
  if (edgeType(edge) === "audio") return edge.target === undefined && emitsAudio(from.kind) && acceptsAudio(to.kind);
  const occupied = existing.some((item) => edgeType(item) === "modulation"
    && item.to === edge.to && item.target === edge.target);
  return !occupied && controls.has(from.kind) && typeof edge.target === "string"
    && (MODULATION_TARGETS[to.kind]?.includes(edge.target) ?? false);
}

export function hasPlayablePath(instrument: Instrument): boolean {
  const outputs = new Set(instrument.modules.filter((node) => node.kind === "output").map((node) => node.id));
  const pending = instrument.modules.filter((node) => sources.has(node.kind)).map((node) => node.id);
  const visited = new Set<string>();
  while (pending.length) {
    const id = pending.shift() as string;
    if (outputs.has(id)) return true;
    if (!visited.has(id)) {
      visited.add(id);
      pending.push(...instrument.connections.filter((edge) => edgeType(edge) === "audio" && edge.from === id)
        .map((edge) => edge.to));
    }
  }
  return false;
}

function waveformOf(saved: Record<string, unknown>, version: StateVersion): WaveformShape | null {
  if (version >= 5)
    if (version >= 9 && saved.waveform === undefined) return "sine";
  if (version >= 5)
    return ["sine", "square", "saw", "triangle"].includes(saved.waveform as string)
      ? saved.waveform as WaveformShape : null;
  if (!Array.isArray(saved.samples) || saved.samples.length !== SAMPLE_COUNT
      || !saved.samples.every((sample) => finite(sample) && sample >= -1 && sample <= 1)) return null;
  const shapes: WaveformShape[] = ["sine", "square", "saw", "triangle"];
  return shapes.reduce((best, shape) => {
    const error = waveformSamples(shape).reduce((sum, sample, index) =>
      sum + (sample - (saved.samples as number[])[index]!) ** 2, 0);
    return error < best.error ? { shape, error } : best;
  }, { shape: "sine" as WaveformShape, error: Number.POSITIVE_INFINITY }).shape;
}
function sequence(saved: Record<string, unknown>, version: StateVersion, instruments: Set<string>
    ): Pick<LabState, "notes" | "bpm" | "volume"> | null {
  if (!Array.isArray(saved.notes) || !finite(saved.bpm) || saved.notes.length !== STEP_COUNT) return null;
  const notes: SequencedNote[][] = [];
  for (const step of saved.notes) {
    if (!Array.isArray(step)) return null;
    const values = version < 8 ? step.map((pitch) => ({ pitch, instrument: "main" })) : step;
    if (!values.every((note) => record(note) && Number.isInteger(note.pitch) && PITCHES.includes(note.pitch as number)
      && typeof note.instrument === "string" && instruments.has(note.instrument))) return null;
    const keys = values.map((note) => `${(note as SequencedNote).instrument}:${(note as SequencedNote).pitch}`);
    if (new Set(keys).size !== keys.length) return null;
    notes.push(values.map((note) => ({ pitch: (note as SequencedNote).pitch,
      instrument: (note as SequencedNote).instrument })));
  }
  const volume = version < 4 ? 0.8 : saved.volume;
  if (!finite(volume) || volume < 0 || volume > 1) return null;
  return { notes, bpm: Math.max(40, Math.min(240, saved.bpm)), volume };
}
function modulesOf(values: unknown[], version: StateVersion): ModuleNode[] | null {
  if (!values.length || !values.every((value) => validModule(value, version))) return null;
  const modules = values.map((value) => {
    const node = value as ModuleNode;
    if (version === 1) return createModule(node.id, node.kind);
    if (version >= 6) {
      const raw = value as unknown as Record<string, unknown>;
      const parameters = flatParameters(node.kind, raw, version < 9);
      if (!parameters) throw new Error("validated module parameters were not recoverable");
      return { id: node.id, kind: node.kind,
        parameters, ...(bypassable.has(node.kind) ? { bypass: node.bypass ?? false } : {}) };
    }
    return { id: node.id, kind: node.kind, parameters: { ...node.parameters },
      ...(node.bypass === undefined ? {} : { bypass: node.bypass }) };
  });
  return new Set(modules.map((node) => node.id)).size === modules.length ? modules : null;
}
function connectionsOf(values: unknown[], modules: ModuleNode[], legacy: boolean): Connection[] | null {
  const result: Connection[] = [];
  for (const value of values) {
    if (!record(value) || typeof value.from !== "string" || typeof value.to !== "string") return null;
    const edge: Connection = legacy || value.type === undefined ? { from: value.from, to: value.to, type: "audio" }
      : { from: value.from, to: value.to, type: value.type as ConnectionType,
        ...(value.target === undefined ? {} : { target: value.target as string }) };
    const duplicate = result.some((item) => edgeType(item) === edgeType(edge) && item.from === edge.from
      && item.to === edge.to && item.target === edge.target);
    if ((!legacy && edge.type !== "audio" && edge.type !== "modulation") || duplicate
      || !validConnection(modules, edge, result)) return null;
    result.push(edge);
  }
  return result;
}

function embeddedConnections(values: unknown[]): unknown[] | null {
  const connections: unknown[] = [];
  for (const value of values) {
    if (!record(value)) return null;
    const embedded = value.connections ?? [];
    if (!Array.isArray(embedded)) return null;
    for (const edge of embedded) {
      if (!record(edge) || edge.from !== value.id) return null;
      connections.push(edge);
    }
  }
  return connections;
}

function instrumentOf(value: unknown, version: StateVersion, mappedName?: string): Instrument | null {
  if (!record(value) || !/^#[0-9a-fA-F]{6}$/.test(value.color as string)
      || !Array.isArray(value.modules)) return null;
  const name = mappedName ?? value.name;
  if (typeof name !== "string" || !name.trim()) return null;
  const fields = mappedName ? ["color", "waveform", "output", "modules"]
    : ["name", "color", "waveform", "modules"];
  if (Object.keys(value).some((key) => !fields.includes(key))) return null;
  if (version === STATE_VERSION && value.modules.some((module) =>
    record(module) && (module.id === "output" || module.kind === "output"))) return null;
  const parsedModules = modulesOf(value.modules, version);
  let reservedOutput = createModule("output", "output");
  if (version === STATE_VERSION && value.output !== undefined) {
    if (!record(value.output) || Object.keys(value.output).some((field) => field !== "level")
      || !finite(value.output.level) || value.output.level < 0 || value.output.level > 1) return null;
    reservedOutput = { ...reservedOutput, parameters: { level: value.output.level } };
  }
  const modules = parsedModules && version === STATE_VERSION
    ? [...parsedModules, reservedOutput] : parsedModules;
  const embedded = embeddedConnections(value.modules);
  const waveform = waveformOf(value, version);
  if (!modules || !embedded || !waveform) return null;
  const connections = connectionsOf(embedded, modules, false);
  return connections ? { name, color: value.color as string,
    waveform, modules, connections } : null;
}

function withReservedOutput(instrument: Instrument): Instrument | null {
  const outputs = instrument.modules.filter((module) => module.kind === "output");
  if (outputs.length !== 1) return null;
  const output = outputs[0] as ModuleNode;
  if (output.id !== "output" && instrument.modules.some((module) => module.id === "output")) return null;
  return { ...instrument,
    modules: instrument.modules.map((module) => module === output
      ? { ...output, id: "output" } : module),
    connections: instrument.connections.map((edge) => ({ ...edge,
      from: edge.from === output.id ? "output" : edge.from,
      to: edge.to === output.id ? "output" : edge.to })) };
}

function flattened(value: Record<string, unknown>): Record<string, unknown> | null {
  if (value.version === 1) return value;
  if (value.version !== 2 && value.version !== 3 && value.version !== 4 && value.version !== 5
      && value.version !== 6 && value.version !== 7 && value.version !== 8
      && value.version !== 9 && value.version !== 10 && value.version !== STATE_VERSION) return null;
  if (!record(value.synth) || !record(value.loop)) return value;
  return { version: value.version, ...value.synth, ...value.loop };
}

/** Validates current nested YAML data or legacy flat state without manufacturing a fallback. */
export function validatedState(value: unknown): LabState | null {
  if (!record(value)) return null;
  const saved = flattened(value);
  if (!saved || (saved.version !== 1 && saved.version !== 2 && saved.version !== 3 && saved.version !== 4
      && saved.version !== 5 && saved.version !== 6 && saved.version !== 7 && saved.version !== 8
      && saved.version !== 9 && saved.version !== 10 && saved.version !== STATE_VERSION)) return null;
  const version = saved.version as StateVersion;
  if (version === STATE_VERSION) {
    if (!record(saved.loop)) return null;
    const entries = Object.entries(saved).filter(([name]) => name !== "version" && name !== "loop");
    if (!entries.length) return null;
    const instruments = entries.map(([name, instrument]) => instrumentOf(instrument, version, name));
    if (instruments.some((instrument) => !instrument)) return null;
    const validInstruments = instruments as Instrument[];
    const sequencer = sequence(saved.loop as Record<string, unknown>, version, new Set(entries.map(([name]) => name)));
    return sequencer ? { version: STATE_VERSION, instruments: validInstruments, ...sequencer } : null;
  }
  if (version >= 8) {
    if (!Array.isArray(saved.instruments) || !saved.instruments.length) return null;
    const instruments = saved.instruments.map((instrument) => instrumentOf(instrument, version));
    if (instruments.some((instrument) => !instrument)) return null;
    const migratedInstruments = (instruments as Instrument[]).map(withReservedOutput);
    if (migratedInstruments.some((instrument) => !instrument)) return null;
    const validInstruments = migratedInstruments as Instrument[];
    const names = validInstruments.map((instrument) => instrument.name);
    if (new Set(names).size !== names.length) return null;
    const sequencer = sequence(saved, version, new Set(names));
    return sequencer ? { version: STATE_VERSION, instruments: validInstruments, ...sequencer } : null;
  }
  if (!Array.isArray(saved.modules)) return null;
  const legacy = version === 1;
  const connectionValues = version === 7 ? embeddedConnections(saved.modules) : saved.connections;
  if (!Array.isArray(connectionValues)) return null;
  const modules = modulesOf(saved.modules, version);
  const sequencer = sequence(saved, version, new Set(["main"]));
  const waveform = waveformOf(saved, version);
  if (!modules || !sequencer || !waveform) return null;
  const connections = connectionsOf(connectionValues, modules, legacy);
  const migrated = connections ? { name: "main", color: "#b8bb26", waveform, modules, connections } : null;
  const instruments = migrated ? [withReservedOutput(migrated)] : null;
  if (instruments?.some((instrument) => !instrument)) return null;
  return instruments ? { version: STATE_VERSION, instruments: instruments as Instrument[], ...sequencer } : null;
}

/** Restores current YAML data or atomically migrates valid legacy state; defects return a fresh patch. */
export function restoreState(value: unknown): LabState { return validatedState(value) ?? initialState(); }

export function midiLabel(midi: number): string {
  const names = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"];
  return `${names[midi % 12]}${Math.floor(midi / 12) - 1}`;
}
export function isNaturalPitch(midi: number): boolean {
  return [0, 2, 4, 5, 7, 9, 11].includes(midi % 12);
}
