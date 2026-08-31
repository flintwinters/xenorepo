import { MODULE_REGISTRY, acceptsAudio, emitsAudio, emitsControl, isModuleKind, isSource,
  modulationTargets, moduleDefinition, registryDefaults, type ModuleKind, type ParameterValue } from "./module-registry.js";
import { freshInstruments } from "./presets.js";

export const STEP_COUNT = 32;
export const STATE_VERSION = 14 as const;
export { MODULE_REGISTRY, acceptsAudio, emitsAudio, emitsControl, modulationTargets };
export type { ModuleKind };
export type ConnectionType = "audio" | "modulation";
export type ModuleParameters = Record<string, ParameterValue>;
export interface ModuleNode { id: string; kind: ModuleKind; parameters: ModuleParameters; bypass?: boolean; }
export interface Connection { from: string; to: string; type?: ConnectionType; target?: string; amount?: number; }
export interface Instrument { name: string; color: string; modules: ModuleNode[]; connections: Connection[]; }
export interface SequencedNote { pitch: number; instrument: string; }
export interface LabState { version: 14; instruments: Instrument[]; notes: SequencedNote[][]; bpm: number; volume: number; }

const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const record = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);
export function pitchesForTopOctave(octave: number): number[] {
  const top = (octave + 1) * 12 + 11; return Array.from({ length: 48 }, (_, index) => top - index);
}
export function isSafeTopOctave(octave: number): boolean {
  return Number.isSafeInteger(octave) && pitchesForTopOctave(octave).every(Number.isSafeInteger);
}
export function defaultParameters(kind: ModuleKind): ModuleParameters { return registryDefaults(kind); }
export function createModule(id: string, kind: ModuleKind): ModuleNode {
  return { id, kind, parameters: defaultParameters(kind),
    ...(MODULE_REGISTRY[kind].bypassable ? { bypass: false } : {}) };
}
export function initialState(): LabState {
  return { version: 14, instruments: freshInstruments(), notes: Array.from({ length: STEP_COUNT }, () => []),
    bpm: 120, volume: 0.8 };
}
export function waveformSamples(kind: string): number[] {
  return Array.from({ length: 128 }, (_, index) => { const phase = index / 128;
    if (kind === "sine") return Math.sin(phase * Math.PI * 2);
    if (kind === "square") return phase < 0.5 ? 1 : -1;
    if (kind === "saw") return 1 - phase * 2; return 1 - 4 * Math.abs(phase - 0.5); });
}

function validParameter(value: unknown, definition: { range?: readonly [number, number]; values?: readonly string[] }
  ): boolean {
  if (definition.values) return typeof value === "string" && definition.values.includes(value);
  return finite(value) && Boolean(definition.range) && value >= definition.range![0] && value <= definition.range![1];
}
function parseModule(value: unknown): ModuleNode | null {
  if (!record(value) || typeof value.id !== "string" || !value.id || !isModuleKind(value.kind)) return null;
  const definition = MODULE_REGISTRY[value.kind];
  const allowed = new Set(["id", "kind", "connections", "bypass", ...Object.keys(definition.parameters)]);
  if (Object.keys(value).some((name) => !allowed.has(name))) return null;
  if ((!definition.bypassable && value.bypass !== undefined)
    || (value.bypass !== undefined && typeof value.bypass !== "boolean")) return null;
  const parameters = defaultParameters(value.kind);
  for (const [name, parameter] of Object.entries(definition.parameters)) {
    if (value[name] !== undefined && !validParameter(value[name], parameter)) return null;
    if (value[name] !== undefined) parameters[name] = value[name] as ParameterValue;
  }
  return { id: value.id, kind: value.kind, parameters,
    ...(definition.bypassable ? { bypass: (value.bypass as boolean | undefined) ?? false } : {}) };
}
function createsCycle(connections: Connection[], candidate: Connection): boolean {
  const adjacency = new Map<string, string[]>();
  for (const edge of [...connections, candidate]) adjacency.set(edge.from, [...(adjacency.get(edge.from) ?? []), edge.to]);
  const pending = [candidate.to]; const visited = new Set<string>();
  while (pending.length) { const id = pending.pop() as string; if (id === candidate.from) return true;
    if (!visited.has(id)) { visited.add(id); pending.push(...(adjacency.get(id) ?? [])); } }
  return false;
}
export function validConnection(modules: ModuleNode[], edge: Connection, existing: Connection[] = []): boolean {
  const from = modules.find((node) => node.id === edge.from); const to = modules.find((node) => node.id === edge.to);
  if (!from || !to || from.id === to.id || createsCycle(existing, edge)) return false;
  if ((edge.type ?? "audio") === "audio")
    return edge.target === undefined && edge.amount === undefined && emitsAudio(from.kind) && acceptsAudio(to.kind);
  const occupied = existing.some((item) => item.type === "modulation"
    && item.to === edge.to && item.target === edge.target);
  return edge.type === "modulation" && !occupied && emitsControl(from.kind) && typeof edge.target === "string"
    && modulationTargets(to.kind).includes(edge.target) && (edge.amount === undefined || finite(edge.amount));
}
function parseConnection(value: unknown, owner: string, modules: ModuleNode[], existing: Connection[]
  ): Connection | null {
  if (!record(value) || value.from !== owner || typeof value.to !== "string"
    || Object.keys(value).some((name) => !["from", "to", "type", "target", "amount"].includes(name))) return null;
  const edge = { from: owner, to: value.to,
    ...(value.type === undefined ? {} : { type: value.type as ConnectionType }),
    ...(value.target === undefined ? {} : { target: value.target as string }),
    ...(value.amount === undefined ? {} : { amount: value.amount as number }) };
  const duplicate = existing.some((item) => (item.type ?? "audio") === (edge.type ?? "audio")
    && item.from === edge.from && item.to === edge.to && item.target === edge.target);
  return !duplicate && validConnection(modules, edge, existing) ? edge : null;
}
function parseInstrument(name: string, value: unknown): Instrument | null {
  if (!record(value) || !/^#[\da-fA-F]{6}$/.test(value.color as string) || !Array.isArray(value.modules)
    || Object.keys(value).some((key) => !["color", "output", "modules"].includes(key))) return null;
  const parsed = value.modules.map(parseModule); if (parsed.some((module) => !module)) return null;
  const modules = parsed as ModuleNode[];
  if (!modules.length || new Set(modules.map((module) => module.id)).size !== modules.length
    || modules.some((module) => module.kind === "output" || module.id === "output")) return null;
  const output = createModule("output", "output");
  if (value.output !== undefined) {
    if (!record(value.output) || Object.keys(value.output).some((key) => key !== "level")
      || (value.output.level !== undefined
        && !validParameter(value.output.level, MODULE_REGISTRY.output.parameters.level))) return null;
    if (value.output.level !== undefined) output.parameters.level = value.output.level as number;
  }
  const complete = [...modules, output]; const connections: Connection[] = [];
  for (const raw of value.modules) { if (!record(raw)
      || (raw.connections !== undefined && !Array.isArray(raw.connections))) return null;
    for (const item of (raw.connections as unknown[] | undefined) ?? []) {
      const edge = parseConnection(item, raw.id as string, complete, connections); if (!edge) return null;
      connections.push(edge);
    } }
  return { name, color: value.color as string, modules: complete, connections };
}
function parseSequence(value: unknown, names: Set<string>): Pick<LabState, "notes" | "bpm" | "volume"> | null {
  if (!record(value) || !Array.isArray(value.notes) || value.notes.length !== STEP_COUNT || !finite(value.bpm)) return null;
  const notes: SequencedNote[][] = [];
  for (const step of value.notes) { if (!Array.isArray(step)) return null;
    if (!step.every((note) => record(note) && Number.isSafeInteger(note.pitch)
      && typeof note.instrument === "string" && names.has(note.instrument))) return null;
    const values = step as unknown as SequencedNote[];
    if (new Set(values.map((note) => `${note.instrument}:${note.pitch}`)).size !== values.length) return null;
    notes.push(values.map((note) => ({ ...note }))); }
  return finite(value.volume) && value.volume >= 0 && value.volume <= 1
    ? { notes, bpm: Math.max(40, Math.min(240, value.bpm)), volume: value.volume } : null;
}
function parseCurrent(value: Record<string, unknown>): LabState | null {
  if (value.version !== 14 || !record(value.loop)) return null;
  const entries = Object.entries(value).filter(([name]) => name !== "version" && name !== "loop");
  const instruments = entries.map(([name, raw]) => parseInstrument(name, raw));
  if (!entries.length || instruments.some((item) => !item)) return null;
  const sequence = parseSequence(value.loop, new Set(entries.map(([name]) => name)));
  return sequence ? { version: 14, instruments: instruments as Instrument[], ...sequence } : null;
}

const LEGACY_KIND: Record<string, ModuleKind> = { waveform: "oscillator", adsr: "envelope" };
const ENUMS: Record<string, readonly string[]> = { "filter:mode": ["low-pass", "high-pass", "band-pass", "notch"],
  "noise:color": ["white", "pink", "brown"], "lfo:shape": ["sine", "triangle", "square", "saw"] };
function migrateModule(raw: unknown, shape: unknown): Record<string, unknown> | null {
  if (!record(raw) || typeof raw.id !== "string" || typeof raw.kind !== "string") return null;
  const kind = LEGACY_KIND[raw.kind] ?? raw.kind; if (!isModuleKind(kind)) return null;
  const source = record(raw.parameters) ? raw.parameters : raw; const values: Record<string, unknown> = {};
  for (const name of Object.keys(MODULE_REGISTRY[kind].parameters)) { const value = source[name];
    values[name] = value === undefined ? moduleDefinition(kind).parameters[name]!.default
      : ENUMS[`${kind}:${name}`] && finite(value) ? ENUMS[`${kind}:${name}`]![Math.round(value)] : value; }
  if (kind === "oscillator") { const cents = finite(source.detune) ? source.detune : 0;
    values.shape = typeof source.shape === "string" ? source.shape : typeof shape === "string" ? shape : "sine";
    values.octave = finite(source.octave) ? source.octave : Math.trunc(cents / 1200);
    values.semitone = finite(source.semitone) ? source.semitone : 0;
    values.detune = Math.max(-100, Math.min(100, cents - (values.octave as number) * 1200)); }
  return { id: raw.id, kind, ...values, ...(MODULE_REGISTRY[kind].bypassable && raw.bypass ? { bypass: true } : {}),
    ...(Array.isArray(raw.connections) ? { connections: raw.connections } : {}) };
}
function migrateInstrument(raw: unknown, external?: unknown[]): Record<string, unknown> | null {
  if (!record(raw) || !Array.isArray(raw.modules)) return null;
  const modules: Record<string, unknown>[] = []; let outputId = "output"; let output: object | undefined;
  for (const item of raw.modules) { const module = migrateModule(item, raw.waveform); if (!module) return null;
    if (module.kind === "output") { outputId = module.id as string; output = { level: module.level }; } else modules.push(module); }
  for (const module of modules) if (Array.isArray(module.connections)) module.connections = module.connections.map((edge) =>
    record(edge) && edge.to === outputId ? { ...edge, to: "output" } : edge);
  for (const edge of external ?? (Array.isArray(raw.connections) ? raw.connections : [])) {
    if (!record(edge) || typeof edge.from !== "string") return null;
    const owner = modules.find((module) => module.id === edge.from); if (!owner) return null;
    owner.connections = [...((owner.connections as unknown[] | undefined) ?? []),
      { ...edge, to: edge.to === outputId ? "output" : edge.to }]; }
  return { color: typeof raw.color === "string" ? raw.color : "#b8bb26", ...(output ? { output } : {}), modules };
}
function migrate(value: Record<string, unknown>): Record<string, unknown> | null {
  if (!Number.isInteger(value.version) || (value.version as number) < 1 || (value.version as number) > 13) return null;
  const flat = record(value.synth) && record(value.loop) ? { ...value.synth, loop: value.loop } : value;
  const result: Record<string, unknown> = { version: 14 }; let loop: unknown;
  if ((value.version as number) >= 11) { for (const [name, raw] of Object.entries(flat)) {
      if (name === "version" || name === "loop") continue; const instrument = migrateInstrument(raw);
      if (!instrument) return null; result[name] = instrument; } loop = flat.loop;
  } else if ((value.version as number) >= 8 && Array.isArray(flat.instruments)) {
    for (const raw of flat.instruments) { if (!record(raw) || typeof raw.name !== "string") return null;
      const instrument = migrateInstrument(raw); if (!instrument) return null; result[raw.name] = instrument; }
    loop = { bpm: flat.bpm, volume: flat.volume ?? 0.8, notes: flat.notes };
  } else { const instrument = migrateInstrument(flat, Array.isArray(flat.connections) ? flat.connections : undefined);
    if (!instrument) return null; result.main = instrument; const notes = Array.isArray(flat.notes)
      ? flat.notes.map((step) => Array.isArray(step) ? step.map((pitch) => ({ pitch, instrument: "main" })) : step) : flat.notes;
    loop = { bpm: flat.bpm, volume: flat.volume ?? 0.8, notes }; }
  result.loop = loop; return result;
}
function wasDefault(state: LabState, version: number): boolean { const signature = state.instruments.map((instrument) =>
  [instrument.name, instrument.modules.filter((module) => module.kind !== "output").map((module) => module.id)]);
  return version === 11 && JSON.stringify(signature) === JSON.stringify([["main", ["waveform-1", "gain-1"]]])
    || version === 12 && JSON.stringify(signature) === JSON.stringify([["main", ["waveform-1", "gain-1"]],
      ["bass", ["bass-waveform-1", "bass-gain-1"]]]); }
export function validatedState(value: unknown): LabState | null {
  if (!record(value)) return null; if (value.version === 14) return parseCurrent(value);
  const document = migrate(value); const state = document && parseCurrent(document); if (!state) return null;
  if (!wasDefault(state, value.version as number)) return state;
  return { ...state, instruments: freshInstruments(), notes: state.notes.map((step) => step.map((note) =>
    ({ ...note, instrument: note.instrument === "main" ? "lead" : note.instrument }))) };
}
export function restoreState(value: unknown): LabState { return validatedState(value) ?? initialState(); }
export function hasPlayablePath(instrument: Instrument): boolean { const outputs = new Set(instrument.modules
    .filter((node) => node.kind === "output").map((node) => node.id));
  const pending = instrument.modules.filter((node) => isSource(node.kind)).map((node) => node.id); const seen = new Set<string>();
  while (pending.length) { const id = pending.shift() as string; if (outputs.has(id)) return true;
    if (!seen.has(id)) { seen.add(id); pending.push(...instrument.connections.filter((edge) =>
      (edge.type ?? "audio") === "audio" && edge.from === id).map((edge) => edge.to)); } } return false; }
export function midiLabel(midi: number): string { const names = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"];
  return `${names[((midi % 12) + 12) % 12]}${Math.floor(midi / 12) - 1}`; }
export function isNaturalPitch(midi: number): boolean {
  return [0, 2, 4, 5, 7, 9, 11].includes(((midi % 12) + 12) % 12); }
