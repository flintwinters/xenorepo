export type ParameterValue = number | string;

export interface ParameterDefinition {
  readonly default: ParameterValue;
  readonly description: string;
  readonly range?: readonly [number, number];
  readonly values?: readonly string[];
  readonly modulatable?: boolean;
}

export interface ModuleDefinition {
  readonly description: string;
  readonly role: "source" | "control" | "processor" | "routing" | "output";
  readonly bypassable: boolean;
  readonly parameters: Readonly<Record<string, ParameterDefinition>>;
}

const numberParameter = (defaultValue: number, range: readonly [number, number], description: string,
  modulatable = true): ParameterDefinition => ({ default: defaultValue, range, description, modulatable });
const enumParameter = (defaultValue: string, values: readonly string[], description: string
  ): ParameterDefinition => ({ default: defaultValue, values, description });

export const MODULE_REGISTRY = {
  oscillator: { description: "Tuned periodic audio source", role: "source", bypassable: false,
    parameters: {
      shape: enumParameter("sine", ["sine", "square", "saw", "triangle"], "Periodic waveform shape"),
      octave: numberParameter(0, [-4, 4], "Whole-octave pitch offset", false),
      semitone: numberParameter(0, [-12, 12], "Semitone pitch offset", false),
      detune: numberParameter(0, [-100, 100], "Fine tuning in cents"),
    } },
  noise: { description: "Colored noise audio source", role: "source", bypassable: false,
    parameters: {
      color: enumParameter("white", ["white", "pink", "brown"], "Noise spectrum color"),
      level: numberParameter(0.25, [0, 1], "Source level"),
    } },
  envelope: { description: "Triggered ADSR audio and control envelope", role: "control", bypassable: true,
    parameters: {
      attack: numberParameter(0.01, [0.001, 10], "Attack time in seconds"),
      decay: numberParameter(0.15, [0.001, 10], "Decay time in seconds"),
      sustain: numberParameter(0.7, [0, 1], "Sustain level"),
      release: numberParameter(0.3, [0.001, 20], "Release time in seconds"),
    } },
  lfo: { description: "Low-frequency modulation source", role: "control", bypassable: false,
    parameters: {
      shape: enumParameter("sine", ["sine", "triangle", "square", "saw"], "LFO waveform shape"),
      rate: numberParameter(2, [0.01, 30], "Cycles per second"),
      depth: numberParameter(0.5, [0, 1], "Normalized LFO depth", false),
    } },
  filter: { description: "Resonant multimode filter", role: "processor", bypassable: true,
    parameters: {
      mode: enumParameter("low-pass", ["low-pass", "high-pass", "band-pass", "notch"], "Filter response"),
      frequency: numberParameter(1200, [20, 20000], "Cutoff frequency in hertz"),
      resonance: numberParameter(1, [0.1, 30], "Filter resonance"),
    } },
  eq: { description: "Three-band equalizer", role: "processor", bypassable: true,
    parameters: {
      low: numberParameter(0, [-24, 24], "Low shelf gain in decibels"),
      mid: numberParameter(0, [-24, 24], "Mid-band gain in decibels"),
      high: numberParameter(0, [-24, 24], "High shelf gain in decibels"),
    } },
  gain: { description: "Linear signal gain", role: "processor", bypassable: false,
    parameters: { gain: numberParameter(0.8, [0, 2], "Linear gain") } },
  saturation: { description: "Parallel nonlinear waveshaper", role: "processor", bypassable: true,
    parameters: {
      drive: numberParameter(2, [1, 20], "Waveshaper drive"),
      mix: numberParameter(0.5, [0, 1], "Wet signal proportion"),
    } },
  compressor: { description: "Dynamic range compressor", role: "processor", bypassable: true,
    parameters: {
      threshold: numberParameter(-24, [-100, 0], "Threshold in decibels"),
      ratio: numberParameter(4, [1, 20], "Compression ratio"),
      attack: numberParameter(0.01, [0, 1], "Attack time in seconds"),
      release: numberParameter(0.25, [0, 1], "Release time in seconds"),
    } },
  mixer: { description: "Summing and level stage", role: "routing", bypassable: false,
    parameters: { level: numberParameter(1, [0, 2], "Mixed output level") } },
  pan: { description: "Stereo constant-power panner", role: "routing", bypassable: true,
    parameters: { pan: numberParameter(0, [-1, 1], "Stereo position from left to right") } },
  output: { description: "Instrument destination", role: "output", bypassable: false,
    parameters: { level: numberParameter(0.8, [0, 1], "Instrument output level") } },
  delay: { description: "Feedback delay", role: "processor", bypassable: true,
    parameters: {
      time: numberParameter(0.25, [0, 2], "Delay time in seconds"),
      feedback: numberParameter(0.3, [0, 0.95], "Feedback proportion"),
      mix: numberParameter(0.25, [0, 1], "Wet signal proportion"),
    } },
  chorus: { description: "Modulated short delay", role: "processor", bypassable: true,
    parameters: {
      rate: numberParameter(1.5, [0.05, 10], "Modulation cycles per second"),
      depth: numberParameter(0.35, [0, 1], "Delay modulation depth"),
      mix: numberParameter(0.3, [0, 1], "Wet signal proportion"),
    } },
  phaser: { description: "Modulated all-pass phase effect", role: "processor", bypassable: true,
    parameters: {
      rate: numberParameter(0.5, [0.05, 10], "Sweep cycles per second"),
      depth: numberParameter(0.5, [0, 1], "Sweep depth"),
      feedback: numberParameter(0.2, [0, 0.9], "Feedback proportion"),
      mix: numberParameter(0.35, [0, 1], "Wet signal proportion"),
    } },
  reverb: { description: "Deterministic convolution reverb", role: "processor", bypassable: true,
    parameters: {
      decay: numberParameter(2, [0.1, 20], "Impulse decay in seconds", false),
      mix: numberParameter(0.25, [0, 1], "Wet signal proportion"),
    } },
} as const satisfies Record<string, ModuleDefinition>;

export type ModuleKind = keyof typeof MODULE_REGISTRY;
export const MODULE_KINDS = Object.keys(MODULE_REGISTRY) as ModuleKind[];
export const isModuleKind = (value: unknown): value is ModuleKind =>
  typeof value === "string" && MODULE_KINDS.includes(value as ModuleKind);
export const isSource = (kind: ModuleKind): boolean => MODULE_REGISTRY[kind].role === "source";
export const emitsControl = (kind: ModuleKind): boolean => MODULE_REGISTRY[kind].role === "control";
export const acceptsAudio = (kind: ModuleKind): boolean => !["source", "output"].includes(
  MODULE_REGISTRY[kind].role) || kind === "output";
export const emitsAudio = (kind: ModuleKind): boolean => kind !== "output" && kind !== "lfo";
export const modulationTargets = (kind: ModuleKind): string[] => Object.entries(MODULE_REGISTRY[kind].parameters)
  .filter(([, definition]) => definition.modulatable).map(([name]) => name);
export const registryDefaults = (kind: ModuleKind): Record<string, ParameterValue> => Object.fromEntries(
  Object.entries(MODULE_REGISTRY[kind].parameters).map(([name, definition]) => [name, definition.default]));
export const moduleDefinition = (kind: ModuleKind): ModuleDefinition => MODULE_REGISTRY[kind];
