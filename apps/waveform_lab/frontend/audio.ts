import type { LabState } from "./model.js";
import { hasPlayablePath } from "./model.js";

export class SynthEngine {
  private context: AudioContext | null = null;
  private timer: number | null = null;
  private step = 0;
  private voices = new Set<AudioBufferSourceNode>();

  async start(state: () => LabState, onStep: (step: number) => void): Promise<void> {
    this.stop();
    this.context ??= new AudioContext();
    await this.context.resume();
    this.step = 0;
    const tick = (): void => {
      const current = state();
      onStep(this.step);
      if (hasPlayablePath(current)) for (const midi of current.notes[this.step] ?? []) this.play(midi, current);
      this.step = (this.step + 1) % current.notes.length;
      this.timer = window.setTimeout(tick, 60_000 / current.bpm / 4);
    };
    tick();
  }

  stop(): void {
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.timer = null;
    for (const voice of this.voices) { try { voice.stop(); } catch { /* Voice already ended. */ } }
    this.voices.clear();
  }

  private play(midi: number, state: LabState): void {
    if (!this.context) return;
    const buffer = this.context.createBuffer(1, state.samples.length, this.context.sampleRate);
    buffer.copyToChannel(Float32Array.from(state.samples), 0);
    const source = this.context.createBufferSource();
    const gain = this.context.createGain();
    source.buffer = buffer;
    source.loop = true;
    source.playbackRate.value = (440 * 2 ** ((midi - 69) / 12)) * state.samples.length / this.context.sampleRate;
    gain.gain.setValueAtTime(0.0001, this.context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.16, this.context.currentTime + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, this.context.currentTime + 0.12);
    source.connect(gain).connect(this.context.destination);
    source.onended = () => this.voices.delete(source);
    source.start(); source.stop(this.context.currentTime + 0.13); this.voices.add(source);
  }
}
