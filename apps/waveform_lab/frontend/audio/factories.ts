import type { LabState, ModuleNode } from "../model.js";

export interface AudioCaches { noise: Map<string, AudioBuffer>; impulses: Map<string, AudioBuffer>; }
export interface RuntimeModule {
  input?: AudioNode; output?: AudioNode; control?: AudioNode;
  targets: Record<string, AudioParam>; sources: AudioScheduledSourceNode[]; nodes: AudioNode[];
  tail: number;
}
interface BuildContext {
  audio: AudioContext; module: ModuleNode; state: LabState; midi: number;
  now: number; gate: number; chordSize: number; caches: AudioCaches;
}

function value(module: ModuleNode, name: string): number { return module.parameters?.[name] ?? 0; }
function runtime(input?: AudioNode, output?: AudioNode): RuntimeModule {
  return { ...(input ? { input } : {}), ...(output ? { output } : {}), targets: {}, sources: [],
    nodes: [input, output].filter((node): node is AudioNode => Boolean(node)), tail: 0 };
}
function passthrough(audio: AudioContext): RuntimeModule { const node = audio.createGain(); return runtime(node, node); }
function wetDry(audio: AudioContext, effect: AudioNode, mix: number): RuntimeModule {
  const input = audio.createGain(); const output = audio.createGain();
  const dry = audio.createGain(); const wet = audio.createGain();
  dry.gain.value = 1 - mix; wet.gain.value = mix;
  input.connect(dry).connect(output); input.connect(effect).connect(wet).connect(output);
  const built = runtime(input, output); built.nodes.push(effect, dry, wet); built.targets.mix = wet.gain; return built;
}
function periodicBuffer(context: BuildContext): AudioBuffer {
  const buffer = context.audio.createBuffer(1, context.state.samples.length, context.audio.sampleRate);
  buffer.copyToChannel(Float32Array.from(context.state.samples), 0); return buffer;
}
function waveform(context: BuildContext): RuntimeModule {
  const source = context.audio.createBufferSource(); const gain = context.audio.createGain();
  source.buffer = periodicBuffer(context); source.loop = true;
  source.playbackRate.value = (440 * 2 ** ((context.midi - 69) / 12))
    * context.state.samples.length / context.audio.sampleRate;
  source.detune.value = value(context.module, "detune");
  gain.gain.value = 0.16 / Math.sqrt(Math.max(1, context.chordSize)); source.connect(gain);
  return { ...runtime(undefined, gain), targets: { detune: source.detune }, sources: [source], nodes: [source, gain], tail: 0 };
}
function seededNoise(audio: AudioContext, color: number, cache: AudioCaches): AudioBuffer {
  const key = `${audio.sampleRate}:${color}`; const found = cache.noise.get(key); if (found) return found;
  const buffer = audio.createBuffer(1, audio.sampleRate, audio.sampleRate); const data = buffer.getChannelData(0);
  let seed = 0x12345678; let pink = 0; let brown = 0;
  for (let index = 0; index < data.length; index += 1) {
    seed = (1664525 * seed + 1013904223) >>> 0; const white = seed / 0x80000000 - 1;
    pink = pink * 0.92 + white * 0.08; brown = Math.max(-1, Math.min(1, brown + white * 0.02));
    data[index] = color < 0.5 ? white : color < 1.5 ? pink * 3 : brown;
  }
  cache.noise.set(key, buffer); return buffer;
}
function noise(context: BuildContext): RuntimeModule {
  const source = context.audio.createBufferSource(); const gain = context.audio.createGain();
  source.buffer = seededNoise(context.audio, value(context.module, "color"), context.caches); source.loop = true;
  gain.gain.value = value(context.module, "level") / Math.sqrt(Math.max(1, context.chordSize)); source.connect(gain);
  return { ...runtime(undefined, gain), targets: { level: gain.gain }, sources: [source], nodes: [source, gain], tail: 0 };
}
function gainModule(context: BuildContext, parameter = "gain"): RuntimeModule {
  const gain = context.audio.createGain(); gain.gain.value = value(context.module, parameter);
  return { ...runtime(gain, gain), targets: { [parameter]: gain.gain } };
}
function filter(context: BuildContext): RuntimeModule {
  const node = context.audio.createBiquadFilter();
  node.type = (["lowpass", "highpass", "bandpass", "notch"] as const)[Math.round(value(context.module, "mode"))] ?? "lowpass";
  node.frequency.value = value(context.module, "frequency"); node.Q.value = value(context.module, "resonance");
  return { ...runtime(node, node), targets: { frequency: node.frequency, resonance: node.Q } };
}
function adsr(context: BuildContext): RuntimeModule {
  const audioGain = context.audio.createGain(); const constant = context.audio.createConstantSource();
  const envelope = context.audio.createGain(); constant.offset.value = 1; constant.connect(envelope);
  const attack = value(context.module, "attack"); const decay = value(context.module, "decay");
  const sustain = value(context.module, "sustain"); const release = value(context.module, "release");
  for (const param of [audioGain.gain, envelope.gain]) {
    param.setValueAtTime(0, context.now); param.linearRampToValueAtTime(1, context.now + attack);
    param.linearRampToValueAtTime(sustain, context.now + attack + decay);
    param.setValueAtTime(sustain, context.now + context.gate);
    param.linearRampToValueAtTime(0, context.now + context.gate + release);
  }
  return { input: audioGain, output: audioGain, control: envelope, targets: {}, sources: [constant],
    nodes: [audioGain, constant, envelope], tail: release };
}
function saturationCurve(drive: number): Float32Array<ArrayBuffer> {
  const curve = new Float32Array(1024); const amount = Math.max(1, drive);
  for (let index = 0; index < curve.length; index += 1) {
    const x = index * 2 / (curve.length - 1) - 1; curve[index] = Math.tanh(x * amount) / Math.tanh(amount);
  }
  return curve;
}
function saturation(context: BuildContext): RuntimeModule {
  const shaper = context.audio.createWaveShaper(); const drive = context.audio.createGain();
  shaper.curve = saturationCurve(value(context.module, "drive")); shaper.oversample = "4x"; drive.gain.value = value(context.module, "drive");
  const input = context.audio.createGain(); const output = context.audio.createGain();
  const dry = context.audio.createGain(); const wet = context.audio.createGain();
  dry.gain.value = 1 - value(context.module, "mix"); wet.gain.value = value(context.module, "mix");
  input.connect(dry).connect(output); input.connect(drive).connect(shaper).connect(wet).connect(output);
  return { ...runtime(input, output), targets: { drive: drive.gain, mix: wet.gain },
    nodes: [input, output, dry, wet, drive, shaper] };
}
function delay(context: BuildContext): RuntimeModule {
  const node = context.audio.createDelay(2); const feedback = context.audio.createGain();
  node.delayTime.value = value(context.module, "time"); feedback.gain.value = value(context.module, "feedback");
  node.connect(feedback).connect(node); const built = wetDry(context.audio, node, value(context.module, "mix"));
  built.nodes.push(feedback); built.targets.time = node.delayTime; built.targets.feedback = feedback.gain;
  built.tail = Math.min(4, value(context.module, "time") * 6); return built;
}
function impulse(context: BuildContext): AudioBuffer {
  const decay = value(context.module, "decay"); const length = Math.ceil(context.audio.sampleRate * Math.min(decay, 6));
  const key = `${context.audio.sampleRate}:${decay}`; const found = context.caches.impulses.get(key); if (found) return found;
  const buffer = context.audio.createBuffer(2, length, context.audio.sampleRate);
  for (let channel = 0; channel < 2; channel += 1) {
    const data = buffer.getChannelData(channel); let seed = 0x9e3779b9 + channel;
    for (let index = 0; index < length; index += 1) {
      seed = (1664525 * seed + 1013904223) >>> 0;
      data[index] = (seed / 0x80000000 - 1) * (1 - index / length) ** 2;
    }
  }
  context.caches.impulses.set(key, buffer); return buffer;
}
function reverb(context: BuildContext): RuntimeModule {
  const convolver = context.audio.createConvolver(); convolver.buffer = impulse(context);
  const built = wetDry(context.audio, convolver, value(context.module, "mix"));
  built.tail = Math.min(value(context.module, "decay"), 6); return built;
}
function chorus(context: BuildContext): RuntimeModule {
  const delayNode = context.audio.createDelay(0.05); delayNode.delayTime.value = 0.015;
  const oscillator = context.audio.createOscillator(); const depth = context.audio.createGain();
  oscillator.frequency.value = value(context.module, "rate"); depth.gain.value = value(context.module, "depth") * 0.008;
  oscillator.connect(depth).connect(delayNode.delayTime);
  const built = wetDry(context.audio, delayNode, value(context.module, "mix"));
  built.sources.push(oscillator); built.nodes.push(oscillator, depth);
  built.targets.rate = oscillator.frequency; built.targets.depth = depth.gain; built.tail = 0.05; return built;
}
function compressor(context: BuildContext): RuntimeModule {
  const node = context.audio.createDynamicsCompressor();
  node.threshold.value = value(context.module, "threshold"); node.ratio.value = value(context.module, "ratio");
  node.attack.value = value(context.module, "attack"); node.release.value = value(context.module, "release");
  return { ...runtime(node, node), targets: { threshold: node.threshold, ratio: node.ratio,
    attack: node.attack, release: node.release } };
}
function lfo(context: BuildContext): RuntimeModule {
  const oscillator = context.audio.createOscillator(); const depth = context.audio.createGain();
  oscillator.type = (["sine", "triangle", "square", "sawtooth"] as const)[Math.round(value(context.module, "shape"))] ?? "sine";
  oscillator.frequency.value = value(context.module, "rate"); depth.gain.value = value(context.module, "depth"); oscillator.connect(depth);
  return { ...runtime(), control: depth, targets: {}, sources: [oscillator], nodes: [oscillator, depth], tail: 0 };
}

export function buildModule(context: BuildContext): RuntimeModule {
  if (context.module.bypass && context.module.kind !== "adsr") return passthrough(context.audio);
  const factories: Record<ModuleNode["kind"], (value: BuildContext) => RuntimeModule> = {
    waveform, noise, gain: gainModule, output: (item) => gainModule(item, "level"), mixer: (item) => gainModule(item, "level"),
    filter, adsr: (item) => item.module.bypass ? passthrough(item.audio) : adsr(item),
    saturation, delay, reverb, chorus, compressor, lfo,
  };
  return factories[context.module.kind](context);
}
