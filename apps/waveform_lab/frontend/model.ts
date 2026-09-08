import { MODULE_REGISTRY, acceptsAudio, emitsAudio, emitsControl, isModuleKind, isSource,
  modulationTargets, moduleDefinition, registryDefaults, type ModuleKind, type ParameterValue,
} from "./module-registry.js";
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
export interface LabState {
  version: 14; instruments: Instrument[]; notes: SequencedNote[][]; bpm: number; volume: number;
}

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
function validModuleShape(value: Record<string, unknown>, kind: ModuleKind): boolean {
  const definition = MODULE_REGISTRY[kind];
  const allowed = new Set(["id", "kind", "connections", "bypass", ...Object.keys(definition.parameters)]);
  if (Object.keys(value).some((name) => !allowed.has(name))) return false;
  if ((!definition.bypassable && value.bypass !== undefined)
    || (value.bypass !== undefined && typeof value.bypass !== "boolean")) return false;
  return true;
}
function parsedParameters(value: Record<string, unknown>, kind: ModuleKind): ModuleParameters | null {
  const parameters = defaultParameters(kind);
  const definition = MODULE_REGISTRY[kind];
  for (const [name, parameter] of Object.entries(definition.parameters)) {
    if (value[name] !== undefined && !validParameter(value[name], parameter)) return null;
    if (value[name] !== undefined) parameters[name] = value[name] as ParameterValue;
  }
  return parameters;
}
type ModuleRecord = Record<string, unknown> & { id: string; kind: ModuleKind };
function moduleRecord(value: unknown): value is ModuleRecord {
  return record(value) && typeof value.id === "string" && Boolean(value.id) && isModuleKind(value.kind);
}
function parseModule(value: unknown): ModuleNode | null {
  if (!moduleRecord(value)) return null;
  if (!validModuleShape(value, value.kind)) return null;
  const parameters = parsedParameters(value, value.kind); if (!parameters) return null;
  return { id: value.id, kind: value.kind, parameters,
    ...(MODULE_REGISTRY[value.kind].bypassable
      ? { bypass: (value.bypass as boolean | undefined) ?? false } : {}) };
}
function createsCycle(connections: Connection[], candidate: Connection): boolean {
  const adjacency = new Map<string, string[]>();
  for (const edge of [...connections, candidate])
    adjacency.set(edge.from, [...(adjacency.get(edge.from) ?? []), edge.to]);
  const pending = [candidate.to]; const visited = new Set<string>();
  while (pending.length) { const id = pending.pop() as string; if (id === candidate.from) return true;
    if (!visited.has(id)) { visited.add(id); pending.push(...(adjacency.get(id) ?? [])); } }
  return false;
}
function validAudioConnection(from: ModuleNode, to: ModuleNode, edge: Connection): boolean {
  return edge.target === undefined && edge.amount === undefined
    && emitsAudio(from.kind) && acceptsAudio(to.kind);
}
function validModulationConnection(from: ModuleNode, to: ModuleNode, edge: Connection,
  existing: Connection[]): boolean {
  const occupied = existing.some((item) => item.type === "modulation"
    && item.to === edge.to && item.target === edge.target);
  return edge.type === "modulation" && !occupied && emitsControl(from.kind) && typeof edge.target === "string"
    && modulationTargets(to.kind).includes(edge.target) && (edge.amount === undefined || finite(edge.amount));
}
export function validConnection(modules: ModuleNode[], edge: Connection, existing: Connection[] = []): boolean {
  const from = modules.find((node) => node.id === edge.from);
  const to = modules.find((node) => node.id === edge.to);
  if (!from || !to || from.id === to.id || createsCycle(existing, edge)) return false;
  return (edge.type ?? "audio") === "audio"
    ? validAudioConnection(from, to, edge) : validModulationConnection(from, to, edge, existing);
}
function connectionValue(value: Record<string, unknown>, owner: string): Connection {
  return { from: owner, to: value.to as string,
    ...(value.type === undefined ? {} : { type: value.type as ConnectionType }),
    ...(value.target === undefined ? {} : { target: value.target as string }),
    ...(value.amount === undefined ? {} : { amount: value.amount as number }) };
}
function duplicateConnection(existing: Connection[], edge: Connection): boolean {
  return existing.some((item) => (item.type ?? "audio") === (edge.type ?? "audio")
    && item.from === edge.from && item.to === edge.to && item.target === edge.target);
}
function parseConnection(value: unknown, owner: string, modules: ModuleNode[], existing: Connection[]
  ): Connection | null {
  if (!record(value) || value.from !== owner || typeof value.to !== "string"
    || Object.keys(value).some((name) => !["from", "to", "type", "target", "amount"].includes(name))) return null;
  const edge = connectionValue(value, owner);
  return !duplicateConnection(existing, edge) && validConnection(modules, edge, existing) ? edge : null;
}
function parseModules(values: unknown[]): ModuleNode[] | null {
  const parsed = values.map(parseModule); if (parsed.some((module) => !module)) return null;
  const modules = parsed as ModuleNode[];
  if (!modules.length || new Set(modules.map((module) => module.id)).size !== modules.length) return null;
  return modules.some((module) => module.kind === "output" || module.id === "output") ? null : modules;
}
function parseOutput(value: unknown): ModuleNode | null {
  const output = createModule("output", "output");
  if (value === undefined) return output;
  if (!record(value) || Object.keys(value).some((key) => key !== "level")) return null;
  const level = value.level;
  if (level !== undefined && !validParameter(level, MODULE_REGISTRY.output.parameters.level)) return null;
  if (level !== undefined) output.parameters.level = level as number;
  return output;
}
function parseConnections(values: unknown[], modules: ModuleNode[]): Connection[] | null {
  const connections: Connection[] = [];
  for (const raw of values) {
    if (!record(raw) || (raw.connections !== undefined && !Array.isArray(raw.connections))) return null;
    for (const item of (raw.connections as unknown[] | undefined) ?? []) {
      const edge = parseConnection(item, raw.id as string, modules, connections);
      if (!edge) return null;
      connections.push(edge);
    }
  }
  return connections;
}
function parseInstrument(name: string, value: unknown): Instrument | null {
  if (!record(value) || !/^#[\da-fA-F]{6}$/.test(value.color as string) || !Array.isArray(value.modules)
    || Object.keys(value).some((key) => !["color", "output", "modules"].includes(key))) return null;
  const modules = parseModules(value.modules); const output = parseOutput(value.output);
  if (!modules || !output) return null;
  const complete = [...modules, output]; const connections = parseConnections(value.modules, complete);
  if (!connections) return null;
  return { name, color: value.color as string, modules: complete, connections };
}
function parseStep(value: unknown, names: Set<string>): SequencedNote[] | null {
  if (!Array.isArray(value)) return null;
  if (!value.every((note) => record(note) && Number.isSafeInteger(note.pitch)
    && typeof note.instrument === "string" && names.has(note.instrument))) return null;
  const notes = value as unknown as SequencedNote[];
  const unique = new Set(notes.map((note) => `${note.instrument}:${note.pitch}`));
  return unique.size === notes.length ? notes.map((note) => ({ ...note })) : null;
}
function sequenceRecord(value: unknown): value is Record<string, unknown> & {
  notes: unknown[]; bpm: number;
} {
  return record(value) && Array.isArray(value.notes)
    && value.notes.length === STEP_COUNT && finite(value.bpm);
}
function validVolume(value: unknown): value is number {
  return finite(value) && value >= 0 && value <= 1;
}
function parseSequence(value: unknown, names: Set<string>): Pick<LabState, "notes" | "bpm" | "volume"> | null {
  if (!sequenceRecord(value)) return null;
  const notes: SequencedNote[][] = [];
  for (const raw of value.notes) {
    const step = parseStep(raw, names); if (!step) return null; notes.push(step);
  }
  return validVolume(value.volume)
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
function migratedValue(kind: ModuleKind, name: string, value: unknown): unknown {
  if (value === undefined) return moduleDefinition(kind).parameters[name]!.default;
  const values = ENUMS[`${kind}:${name}`];
  return values && finite(value) ? values[Math.round(value)] : value;
}
function migrateOscillator(values: Record<string, unknown>, source: Record<string, unknown>,
  shape: unknown): void {
  const cents = finite(source.detune) ? source.detune : 0;
  values.shape = typeof source.shape === "string" ? source.shape
    : typeof shape === "string" ? shape : "sine";
  values.octave = finite(source.octave) ? source.octave : Math.trunc(cents / 1200);
  values.semitone = finite(source.semitone) ? source.semitone : 0;
  values.detune = Math.max(-100, Math.min(100, cents - (values.octave as number) * 1200));
}
function migratedParameters(kind: ModuleKind, source: Record<string, unknown>,
  shape: unknown): Record<string, unknown> {
  const values = Object.fromEntries(Object.keys(MODULE_REGISTRY[kind].parameters)
    .map((name) => [name, migratedValue(kind, name, source[name])]));
  if (kind === "oscillator") migrateOscillator(values, source, shape);
  return values;
}
type LegacyModuleRecord = Record<string, unknown> & { id: string; kind: string };
function legacyModuleRecord(value: unknown): value is LegacyModuleRecord {
  return record(value) && typeof value.id === "string" && typeof value.kind === "string";
}
function addLegacyModuleOptions(migrated: Record<string, unknown>, raw: LegacyModuleRecord,
  kind: ModuleKind): void {
  if (MODULE_REGISTRY[kind].bypassable && raw.bypass) migrated.bypass = true;
  if (Array.isArray(raw.connections)) migrated.connections = raw.connections;
}
function migrateModule(raw: unknown, shape: unknown): Record<string, unknown> | null {
  if (!legacyModuleRecord(raw)) return null;
  const kind = LEGACY_KIND[raw.kind] ?? raw.kind; if (!isModuleKind(kind)) return null;
  const source = record(raw.parameters) ? raw.parameters : raw;
  const migrated: Record<string, unknown> = {
    id: raw.id, kind, ...migratedParameters(kind, source, shape),
  };
  addLegacyModuleOptions(migrated, raw, kind);
  return migrated;
}
function migratedModules(raw: Record<string, unknown>): {
  modules: Record<string, unknown>[]; outputId: string; output?: object;
} | null {
  const modules: Record<string, unknown>[] = []; let outputId = "output"; let output: object | undefined;
  for (const item of raw.modules as unknown[]) {
    const module = migrateModule(item, raw.waveform); if (!module) return null;
    if (module.kind === "output") {
      outputId = module.id as string; output = { level: module.level };
    } else modules.push(module);
  }
  return { modules, outputId, ...(output ? { output } : {}) };
}
function remapConnections(modules: Record<string, unknown>[], outputId: string): void {
  for (const module of modules) {
    if (!Array.isArray(module.connections)) continue;
    module.connections = module.connections.map((edge) =>
      record(edge) && edge.to === outputId ? { ...edge, to: "output" } : edge);
  }
}
function addExternalConnections(modules: Record<string, unknown>[], outputId: string,
  edges: unknown[]): boolean {
  for (const edge of edges) {
    if (!record(edge) || typeof edge.from !== "string") return false;
    const owner = modules.find((module) => module.id === edge.from); if (!owner) return false;
    owner.connections = [...((owner.connections as unknown[] | undefined) ?? []),
      { ...edge, to: edge.to === outputId ? "output" : edge.to }];
  }
  return true;
}
function legacyConnections(raw: Record<string, unknown>, external?: unknown[]): unknown[] {
  if (external) return external;
  return Array.isArray(raw.connections) ? raw.connections : [];
}
function migratedInstrumentResult(raw: Record<string, unknown>,
  migrated: { modules: Record<string, unknown>[]; outputId: string; output?: object }
): Record<string, unknown> {
  const result: Record<string, unknown> = {
    color: typeof raw.color === "string" ? raw.color : "#b8bb26", modules: migrated.modules,
  };
  if (migrated.output) result.output = migrated.output;
  return result;
}
function migrateInstrument(raw: unknown, external?: unknown[]): Record<string, unknown> | null {
  if (!record(raw) || !Array.isArray(raw.modules)) return null;
  const migrated = migratedModules(raw); if (!migrated) return null;
  remapConnections(migrated.modules, migrated.outputId);
  const edges = legacyConnections(raw, external);
  if (!addExternalConnections(migrated.modules, migrated.outputId, edges)) return null;
  return migratedInstrumentResult(raw, migrated);
}
function migrateNamedInstruments(flat: Record<string, unknown>): Record<string, unknown> | null {
  const result: Record<string, unknown> = { version: 14, loop: flat.loop };
  for (const [name, raw] of Object.entries(flat)) {
    if (name === "version" || name === "loop") continue;
    const instrument = migrateInstrument(raw); if (!instrument) return null;
    result[name] = instrument;
  }
  return result;
}
function migrateInstrumentArray(flat: Record<string, unknown>): Record<string, unknown> | null {
  if (!Array.isArray(flat.instruments)) return null;
  const result: Record<string, unknown> = { version: 14 };
  for (const raw of flat.instruments) {
    if (!record(raw) || typeof raw.name !== "string") return null;
    const instrument = migrateInstrument(raw); if (!instrument) return null;
    result[raw.name] = instrument;
  }
  result.loop = record(flat.loop) ? flat.loop
    : { bpm: flat.bpm, volume: flat.volume ?? 0.8, notes: flat.notes };
  return result;
}
function legacyNotes(value: unknown): unknown {
  if (!Array.isArray(value)) return value;
  return value.map((step) => Array.isArray(step)
    ? step.map((pitch) => ({ pitch, instrument: "main" })) : step);
}
function migrateSingleInstrument(flat: Record<string, unknown>): Record<string, unknown> | null {
  const external = Array.isArray(flat.connections) ? flat.connections : undefined;
  const instrument = migrateInstrument(flat, external); if (!instrument) return null;
  return { version: 14, main: instrument,
    loop: { bpm: flat.bpm, volume: flat.volume ?? 0.8, notes: legacyNotes(flat.notes) } };
}
function legacyVersion(value: unknown): number | null {
  return Number.isInteger(value) && (value as number) >= 1 && (value as number) <= 13
    ? value as number : null;
}
function flattenedLegacy(value: Record<string, unknown>): Record<string, unknown> {
  return record(value.synth) && record(value.loop) ? { ...value.synth, loop: value.loop } : value;
}
function migrate(value: Record<string, unknown>): Record<string, unknown> | null {
  const version = legacyVersion(value.version); if (version === null) return null;
  const flat = flattenedLegacy(value);
  if (version >= 11) return migrateNamedInstruments(flat);
  if (version >= 8 && Array.isArray(flat.instruments)) return migrateInstrumentArray(flat);
  return migrateSingleInstrument(flat);
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
  const pending = instrument.modules.filter((node) => isSource(node.kind)).map((node) => node.id);
  const seen = new Set<string>();
  while (pending.length) { const id = pending.shift() as string; if (outputs.has(id)) return true;
    if (!seen.has(id)) { seen.add(id); pending.push(...instrument.connections.filter((edge) =>
      (edge.type ?? "audio") === "audio" && edge.from === id).map((edge) => edge.to)); } } return false; }
export function midiLabel(midi: number): string {
  const names = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"];
  return `${names[((midi % 12) + 12) % 12]}${Math.floor(midi / 12) - 1}`; }
export function isNaturalPitch(midi: number): boolean {
  return [0, 2, 4, 5, 7, 9, 11].includes(((midi % 12) + 12) % 12); }
