export const SAMPLE_COUNT = 128;
export const STEP_COUNT = 32;
export const PITCHES = Array.from({ length: 24 }, (_, index) => 83 - index);

export type ModuleKind = "waveform" | "gain" | "output";
export interface ModuleNode { id: string; kind: ModuleKind; x: number; y: number; }
export interface Connection { from: string; to: string; }
export interface LabState {
  version: 1;
  modules: ModuleNode[];
  connections: Connection[];
  samples: number[];
  notes: number[][];
  bpm: number;
}

const kinds = new Set<ModuleKind>(["waveform", "gain", "output"]);

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
    version: 1,
    modules: [
      { id: "waveform-1", kind: "waveform", x: 28, y: 46 },
      { id: "gain-1", kind: "gain", x: 280, y: 112 },
      { id: "output-1", kind: "output", x: 520, y: 62 },
    ],
    connections: [
      { from: "waveform-1", to: "gain-1" },
      { from: "gain-1", to: "output-1" },
    ],
    samples: preset("sine"), notes: Array.from({ length: STEP_COUNT }, () => []), bpm: 120,
  };
}

function finiteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function validConnection(modules: ModuleNode[], connection: Connection): boolean {
  const from = modules.find((node) => node.id === connection.from);
  const to = modules.find((node) => node.id === connection.to);
  if (!from || !to || from.id === to.id) return false;
  return (from.kind === "waveform" && to.kind === "gain")
    || (from.kind === "gain" && to.kind === "output");
}

export function hasPlayablePath(state: LabState): boolean {
  const waveforms = state.modules.filter((node) => node.kind === "waveform");
  const gains = state.modules.filter((node) => node.kind === "gain");
  const outputs = new Set(state.modules.filter((node) => node.kind === "output").map((node) => node.id));
  return waveforms.some((waveform) => gains.some((gain) =>
    state.connections.some((edge) => edge.from === waveform.id && edge.to === gain.id)
    && state.connections.some((edge) => edge.from === gain.id && outputs.has(edge.to))));
}

export function restoreState(value: unknown): LabState {
  const fallback = initialState();
  if (!value || typeof value !== "object") return fallback;
  const saved = value as Partial<LabState>;
  if (saved.version !== 1 || !Array.isArray(saved.modules) || !Array.isArray(saved.connections)
    || !Array.isArray(saved.samples) || !Array.isArray(saved.notes) || !finiteNumber(saved.bpm)) return fallback;
  const modules = saved.modules.filter((node): node is ModuleNode => Boolean(node)
    && typeof node.id === "string" && kinds.has(node.kind) && finiteNumber(node.x) && finiteNumber(node.y));
  if (!modules.length || modules.length !== saved.modules.length) return fallback;
  const ids = new Set(modules.map((node) => node.id));
  if (ids.size !== modules.length) return fallback;
  const samples = saved.samples.filter(finiteNumber);
  if (samples.length !== SAMPLE_COUNT || samples.some((sample) => sample < -1 || sample > 1)) return fallback;
  if (saved.notes.length !== STEP_COUNT) return fallback;
  const notes = saved.notes.map((step) => Array.isArray(step)
    ? [...new Set(step.filter((pitch): pitch is number => Number.isInteger(pitch) && PITCHES.includes(pitch)))] : []);
  if (notes.some((step, index) => !Array.isArray(saved.notes?.[index]) || step.length !== saved.notes[index].length))
    return fallback;
  const connections = saved.connections.filter((edge): edge is Connection => Boolean(edge)
    && typeof edge.from === "string" && typeof edge.to === "string" && validConnection(modules, edge));
  if (connections.length !== saved.connections.length) return fallback;
  const distinct = new Set(connections.map((edge) => `${edge.from}>${edge.to}`));
  if (distinct.size !== connections.length) return fallback;
  return { version: 1, modules, connections, samples, notes, bpm: Math.max(40, Math.min(240, saved.bpm)) };
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
