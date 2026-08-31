export const SAMPLE_COUNT = 128;
export const STEP_COUNT = 32;
export const STATE_VERSION = 3 as const;
export const PITCHES = Array.from({ length: 24 }, (_, index) => 83 - index);

export type ModuleKind = "waveform" | "gain" | "output" | "filter" | "adsr" | "saturation"
  | "delay" | "reverb" | "mixer" | "chorus" | "compressor" | "noise" | "lfo";
export type ConnectionType = "audio" | "modulation";
export type ModuleParameters = Record<string, number>;
export interface ModuleNode {
  id: string; kind: ModuleKind; x: number; y: number;
  parameters?: ModuleParameters; bypass?: boolean;
}
/** Optional for source compatibility with the v1 UI; absent means audio. */
export interface Connection {
  from: string; to: string; type?: ConnectionType; target?: string;
}
export interface LabState {
  version: typeof STATE_VERSION; modules: ModuleNode[]; connections: Connection[];
  samples: number[]; notes: number[][]; holds: number[][]; bpm: number;
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
export function createModule(id: string, kind: ModuleKind, x: number, y: number): ModuleNode {
  return { id, kind, x, y, parameters: defaultParameters(kind), ...(bypassable.has(kind) ? { bypass: false } : {}) };
}

export function preset(kind: "sine" | "square" | "saw" | "triangle"): number[] {
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
    modules: [createModule("waveform-1", "waveform", 28, 46), createModule("gain-1", "gain", 280, 112),
      createModule("output-1", "output", 520, 62)],
    connections: [{ from: "waveform-1", to: "gain-1", type: "audio" },
      { from: "gain-1", to: "output-1", type: "audio" }],
    samples: preset("sine"), notes: emptySequence(), holds: emptySequence(), bpm: 120,
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
function validModule(value: unknown, legacy: boolean): value is ModuleNode {
  if (!record(value) || typeof value.id !== "string" || !value.id || !kinds.has(value.kind as ModuleKind)
    || !finite(value.x) || !finite(value.y)) return false;
  const kind = value.kind as ModuleKind;
  if (legacy) return ["waveform", "gain", "output"].includes(kind);
  if (!validParameters(kind, value.parameters)) return false;
  return bypassable.has(kind) ? typeof value.bypass === "boolean" : value.bypass === undefined;
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

export function hasPlayablePath(state: LabState): boolean {
  const outputs = new Set(state.modules.filter((node) => node.kind === "output").map((node) => node.id));
  const pending = state.modules.filter((node) => sources.has(node.kind)).map((node) => node.id);
  const visited = new Set<string>();
  while (pending.length) {
    const id = pending.shift() as string;
    if (outputs.has(id)) return true;
    if (!visited.has(id)) {
      visited.add(id);
      pending.push(...state.connections.filter((edge) => edgeType(edge) === "audio" && edge.from === id)
        .map((edge) => edge.to));
    }
  }
  return false;
}

function emptySequence(): number[][] { return Array.from({ length: STEP_COUNT }, () => []); }
function pitchSequence(value: unknown): number[][] | null {
  if (!Array.isArray(value) || value.length !== STEP_COUNT) return null;
  const result: number[][] = [];
  for (const step of value) {
    if (!Array.isArray(step) || !step.every((pitch) => Number.isInteger(pitch) && PITCHES.includes(pitch))
      || new Set(step).size !== step.length) return null;
    result.push([...step].sort((a, b) => a - b));
  }
  return result;
}
function validHolds(notes: number[][], holds: number[][]): boolean {
  for (const pitch of PITCHES) {
    if (holds.every((step) => step.includes(pitch))) return false;
    for (let step = 0; step < STEP_COUNT; step += 1) {
      if (!holds[step]?.includes(pitch)) continue;
      if (notes[step]?.includes(pitch)) return false;
      const previous = (step + STEP_COUNT - 1) % STEP_COUNT;
      if (!notes[previous]?.includes(pitch) && !holds[previous]?.includes(pitch)) return false;
    }
  }
  return true;
}
function sequence(saved: Record<string, unknown>, legacy: boolean): Pick<LabState, "samples" | "notes" | "holds" | "bpm"> | null {
  if (!Array.isArray(saved.samples) || !Array.isArray(saved.notes) || !finite(saved.bpm)) return null;
  if (saved.samples.length !== SAMPLE_COUNT || !saved.samples.every((sample) => finite(sample) && sample >= -1 && sample <= 1)
    ) return null;
  const notes = pitchSequence(saved.notes);
  const holds = legacy ? emptySequence() : pitchSequence(saved.holds);
  if (!notes || !holds || !validHolds(notes, holds)) return null;
  return { samples: [...saved.samples] as number[], notes, holds, bpm: Math.max(40, Math.min(240, saved.bpm)) };
}

export function noteLength(state: Pick<LabState, "notes" | "holds">, step: number, pitch: number): number {
  if (!state.notes[step]?.includes(pitch)) return 0;
  let length = 1;
  while (length < STEP_COUNT && state.holds[(step + length) % STEP_COUNT]?.includes(pitch)) length += 1;
  return length;
}
function modulesOf(values: unknown[], legacy: boolean): ModuleNode[] | null {
  if (!values.length || !values.every((value) => validModule(value, legacy))) return null;
  const modules = values.map((value) => {
    const node = value as ModuleNode;
    return legacy ? createModule(node.id, node.kind, node.x, node.y) : { ...node, parameters: { ...node.parameters } };
  });
  return new Set(modules.map((node) => node.id)).size === modules.length ? modules : null;
}
function connectionsOf(values: unknown[], modules: ModuleNode[], legacy: boolean): Connection[] | null {
  const result: Connection[] = [];
  for (const value of values) {
    if (!record(value) || typeof value.from !== "string" || typeof value.to !== "string") return null;
    const edge: Connection = legacy ? { from: value.from, to: value.to, type: "audio" }
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

/** Restores v3 or atomically migrates a valid v1/v2 patch; every defect returns a fresh patch. */
export function restoreState(value: unknown): LabState {
  const fallback = initialState();
  if (!record(value) || (value.version !== 1 && value.version !== 2 && value.version !== STATE_VERSION)
    || !Array.isArray(value.modules) || !Array.isArray(value.connections)) return fallback;
  const legacyModules = value.version === 1;
  const legacySequence = value.version !== STATE_VERSION;
  const modules = modulesOf(value.modules, legacyModules);
  const sequencer = sequence(value, legacySequence);
  if (!modules || !sequencer) return fallback;
  const connections = connectionsOf(value.connections, modules, legacyModules);
  return connections ? { version: STATE_VERSION, modules, connections, ...sequencer } : fallback;
}

export function drawSamples(samples: number[], from: [number, number], to: [number, number]): number[] {
  const next = [...samples];
  const [start, end] = from[0] <= to[0] ? [from, to] : [to, from];
  const low = Math.max(0, Math.min(SAMPLE_COUNT - 1, Math.round(start[0])));
  const high = Math.max(0, Math.min(SAMPLE_COUNT - 1, Math.round(end[0])));
  for (let index = low; index <= high; index += 1) {
    const ratio = high === low ? 1 : (index - low) / (high - low);
    next[index] = Math.max(-1, Math.min(1, start[1] + (end[1] - start[1]) * ratio));
  }
  return next;
}
export function midiLabel(midi: number): string {
  const names = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"];
  return `${names[midi % 12]}${Math.floor(midi / 12) - 1}`;
}
