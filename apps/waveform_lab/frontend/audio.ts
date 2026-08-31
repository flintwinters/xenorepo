import { hasPlayablePath, type Instrument, type LabState } from "./model.js";
import { moduleDefinition } from "./module-registry.js";
import { buildModule, type AudioCaches, type RuntimeModule } from "./audio/factories.js";

interface VoiceRuntime { sources: AudioScheduledSourceNode[]; nodes: AudioNode[]; cleanupTimer: number; }

export class SynthEngine {
  private context: AudioContext | null = null;
  private scheduler: number | null = null;
  private nextStepTime = 0;
  private step = 0;
  private uiTimers = new Set<number>();
  private voices = new Set<VoiceRuntime>();
  private master: DynamicsCompressorNode | null = null;
  private volume: GainNode | null = null;
  private caches: AudioCaches = { noise: new Map(), impulses: new Map() };

  async start(state: () => LabState, onStep: (step: number) => void): Promise<void> {
    this.stop(); this.context ??= new AudioContext(); await this.context.resume();
    this.master ??= this.createMaster(this.context); this.setVolume(state().volume);
    const context = this.context; const master = this.master;
    this.step = 0; this.nextStepTime = context.currentTime + 0.03;
    const schedule = (): void => {
      if (!this.context) return;
      while (this.nextStepTime < this.context.currentTime + 0.1) {
        const current = state(); const scheduledStep = this.step; const notes = current.notes[scheduledStep] ?? [];
        const uiDelay = Math.max(0, (this.nextStepTime - this.context.currentTime) * 1000);
        const uiTimer = window.setTimeout(() => { this.uiTimers.delete(uiTimer); onStep(scheduledStep); }, uiDelay);
        this.uiTimers.add(uiTimer);
        for (const note of notes) {
          const instrument = current.instruments.find((item) => item.name === note.instrument);
          const chordSize = notes.filter((item) => item.instrument === note.instrument).length;
          if (instrument && hasPlayablePath(instrument))
            this.play(context, master, note.pitch, instrument, current.bpm, chordSize,
              this.nextStepTime, true);
        }
        this.step = (this.step + 1) % current.notes.length;
        this.nextStepTime += 60 / current.bpm / 4;
      }
    };
    schedule(); this.scheduler = window.setInterval(schedule, 25);
  }

  stop(): void {
    if (this.scheduler !== null) window.clearInterval(this.scheduler); this.scheduler = null;
    for (const timer of this.uiTimers) window.clearTimeout(timer); this.uiTimers.clear();
    for (const voice of this.voices) this.disposeVoice(voice); this.voices.clear();
  }

  setVolume(volume: number): void {
    if (!this.context || !this.volume) return;
    this.volume.gain.setValueAtTime(Math.max(0, Math.min(1, volume)), this.context.currentTime);
  }

  async renderLoop(state: LabState): Promise<AudioBuffer> {
    const sampleRate = 44_100; const stepDuration = 60 / state.bpm / 4;
    const duration = state.notes.length * stepDuration + 6.5;
    const audio = new OfflineAudioContext(2, Math.ceil(duration * sampleRate), sampleRate);
    const master = this.createCompressor(audio); const volume = audio.createGain();
    volume.gain.value = state.volume; master.connect(volume).connect(audio.destination);
    const caches: AudioCaches = { noise: new Map(), impulses: new Map() };
    state.notes.forEach((notes, step) => notes.forEach((note) => {
      const instrument = state.instruments.find((item) => item.name === note.instrument);
      const chordSize = notes.filter((item) => item.instrument === note.instrument).length;
      if (instrument && hasPlayablePath(instrument)) this.play(audio, master, note.pitch, instrument,
        state.bpm, chordSize, step * stepDuration, false, caches);
    }));
    return audio.startRendering();
  }

  private createMaster(audio: AudioContext): DynamicsCompressorNode {
    const node = this.createCompressor(audio);
    this.volume = audio.createGain(); node.connect(this.volume).connect(audio.destination);
    return node;
  }

  private createCompressor(audio: BaseAudioContext): DynamicsCompressorNode {
    const node = audio.createDynamicsCompressor(); node.threshold.value = -6; node.knee.value = 6;
    node.ratio.value = 12; node.attack.value = 0.003; node.release.value = 0.12;
    return node;
  }

  private play(context: BaseAudioContext, master: AudioNode, midi: number, instrument: Instrument,
    bpm: number, chordSize: number, now: number, dispose: boolean, caches = this.caches): void {
    const gate = Math.max(0.025, Math.min(0.18, 60 / bpm / 4 * 0.68));
    const modules = new Map(instrument.modules.map((module) => [module.id, module]));
    const runtimes = new Map<string, RuntimeModule>();
    for (const module of instrument.modules) runtimes.set(module.id, buildModule({ audio: context,
      module, midi, now, gate, chordSize, caches }));

    const envelopes = instrument.modules.filter((module) => module.kind === "envelope" && !module.bypass);
    const release = Math.max(0.02, ...envelopes.map((module) => Number(module.parameters.release)));
    const effectiveOutputs = new Map<string, AudioNode>(); const extraNodes: AudioNode[] = [];
    for (const module of instrument.modules) {
      const output = runtimes.get(module.id)?.output; if (!output) continue;
      if (module.kind !== "oscillator" && module.kind !== "noise") {
        effectiveOutputs.set(module.id, output); continue;
      }
      const voiceGate = context.createGain(); voiceGate.gain.setValueAtTime(0, now);
      voiceGate.gain.linearRampToValueAtTime(1, now + 0.003);
      voiceGate.gain.setValueAtTime(1, now + gate + release);
      voiceGate.gain.linearRampToValueAtTime(0, now + gate + release + 0.003);
      output.connect(voiceGate); effectiveOutputs.set(module.id, voiceGate); extraNodes.push(voiceGate);
    }
    for (const edge of instrument.connections.filter((item) => (item.type ?? "audio") === "audio")) {
      const from = effectiveOutputs.get(edge.from); const to = runtimes.get(edge.to)?.input;
      if (from && to) from.connect(to);
    }
    for (const edge of instrument.connections.filter((item) => item.type === "modulation")) {
      const source = runtimes.get(edge.from)?.control; const target = edge.target
        ? runtimes.get(edge.to)?.targets[edge.target] : undefined; const targetModule = modules.get(edge.to);
      const parameter = targetModule && edge.target
        ? moduleDefinition(targetModule.kind).parameters[edge.target] : undefined;
      if (!source || !target || !parameter?.range) continue;
      const depth = context.createGain();
      depth.gain.value = edge.amount ?? (parameter.range[1] - parameter.range[0]) * 0.2;
      source.connect(depth).connect(target); extraNodes.push(depth);
    }
    for (const module of instrument.modules.filter((item) => item.kind === "output"))
      runtimes.get(module.id)?.output?.connect(master);

    const all = [...runtimes.values()]; const sources = all.flatMap((item) => item.sources);
    const nodes = [...all.flatMap((item) => item.nodes), ...extraNodes]; const signalEnd = now + gate + release;
    const tail = Math.max(0.03, ...all.map((item) => item.tail)); const cleanupAt = signalEnd + tail + 0.02;
    for (const source of sources) {
      try { source.start(now); source.stop(cleanupAt); } catch { /* Invalid source is silent. */ }
    }
    if (!dispose) return;
    const cleanupTimer = window.setTimeout(() => {
      const voice = [...this.voices].find((candidate) => candidate.cleanupTimer === cleanupTimer);
      if (voice) { this.disposeVoice(voice); this.voices.delete(voice); }
    }, Math.max(0, (cleanupAt - context.currentTime) * 1000));
    this.voices.add({ sources, nodes, cleanupTimer });
  }

  private disposeVoice(voice: VoiceRuntime): void {
    window.clearTimeout(voice.cleanupTimer);
    for (const source of voice.sources) { try { source.stop(); } catch { /* Source already stopped. */ } }
    for (const node of voice.nodes) { try { node.disconnect(); } catch { /* Node already disconnected. */ } }
  }
}
