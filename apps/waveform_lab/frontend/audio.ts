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
      const notes = current.notes[this.step] ?? [];
      if (hasPlayablePath(current)) for (const midi of notes) this.play(midi, current, notes.length);
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

  private play(midi: number, state: LabState, chordSize: number): void {
    if (!this.context) return;
    const stepSeconds = 60 / state.bpm / 4;
    const voiceSeconds = Math.max(0.025, Math.min(0.09, stepSeconds * 0.62));
    const attackSeconds = Math.min(0.006, voiceSeconds * 0.15);
    const releaseSeconds = Math.min(0.025, voiceSeconds * 0.35);
    const peakGain = 0.18 / Math.sqrt(Math.max(1, chordSize));
    const now = this.context.currentTime;
    const buffer = this.context.createBuffer(1, state.samples.length, this.context.sampleRate);
    buffer.copyToChannel(Float32Array.from(state.samples), 0);
    const source = this.context.createBufferSource();
    const gain = this.context.createGain();
    source.buffer = buffer;
    source.loop = true;
    source.playbackRate.value = (440 * 2 ** ((midi - 69) / 12)) * state.samples.length / this.context.sampleRate;
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(peakGain, now + attackSeconds);
    gain.gain.setValueAtTime(peakGain, now + voiceSeconds - releaseSeconds);
    gain.gain.linearRampToValueAtTime(0, now + voiceSeconds);
    source.connect(gain).connect(this.context.destination);
    source.onended = () => { source.disconnect(); gain.disconnect(); this.voices.delete(source); };
    source.start(now); source.stop(now + voiceSeconds + 0.005); this.voices.add(source);
  }
}
