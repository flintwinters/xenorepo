import { Component, render } from "preact";
import { ConsolePane, ConsoleShell, ConsoleWorkspace, StatusRail, UtilityRail } from "@xenorepo/ui";
import { SynthEngine } from "./audio.js";
import { decodeState, encodeState } from "./state-yaml.js";
import { SynthYamlEditor } from "./yaml-editor.js";
import {
  PITCHES, hasPlayablePath, initialState, isNaturalPitch, midiLabel, type LabState,
} from "./model.js";
import "./styles.css";

const storageKey = "waveform-lab-state-v1";
interface ViewState { lab: LabState; playing: boolean; activeStep: number; selectedInstrument: string; }

function loadState(): LabState {
  const saved = localStorage.getItem(storageKey);
  if (!saved) return initialState();
  const restored = decodeState(saved);
  if (restored) return restored;
  localStorage.removeItem(storageKey); return initialState();
}

class WaveformLab extends Component<Record<string, never>, ViewState> {
  private initial = loadState();
  override state: ViewState = { lab: this.initial, playing: false, activeStep: -1,
    selectedInstrument: this.initial.instruments[0]?.name ?? "" };
  private engine = new SynthEngine();

  override componentWillUnmount(): void { this.engine.stop(); }
  private commit = (lab: LabState): void => {
    const selectedInstrument = lab.instruments.some((item) => item.name === this.state.selectedInstrument)
      ? this.state.selectedInstrument : lab.instruments[0]?.name ?? "";
    this.engine.setVolume(lab.volume); this.setState({ lab, selectedInstrument });
    localStorage.setItem(storageKey, encodeState(lab));
  };
  private togglePlayback = async (): Promise<void> => {
    if (this.state.playing) {
      this.engine.stop(); this.setState({ playing: false, activeStep: -1 }); return;
    }
    await this.engine.start(() => this.state.lab, (activeStep) => this.setState({ activeStep }));
    this.setState({ playing: true });
  };
  private toggleNote(step: number, pitch: number): void {
    const notes = this.state.lab.notes.map((values) => [...values]); const current = notes[step] ?? [];
    const instrument = this.state.selectedInstrument;
    const exists = current.some((note) => note.pitch === pitch && note.instrument === instrument);
    notes[step] = exists ? current.filter((note) => note.pitch !== pitch || note.instrument !== instrument)
      : [...current, { pitch, instrument }].sort((a, b) => a.pitch - b.pitch || a.instrument.localeCompare(b.instrument));
    this.commit({ ...this.state.lab, notes });
  }
  private renderSequencer() {
    const lab = this.state.lab;
    return <ConsolePane class="sequence-pane" title="LOOP / 2 BARS / 4∕4" tone="purple">
      <div class="transport"><button class="play" aria-pressed={this.state.playing} onClick={this.togglePlayback}>
        {this.state.playing ? "■ STOP" : "▶ PLAY"}</button>
        <label>BPM <input aria-label="Tempo in BPM" type="number" min="40" max="240" value={lab.bpm}
          onChange={(event) => this.commit({ ...lab,
            bpm: Math.max(40, Math.min(240, Number(event.currentTarget.value) || 120)),
          })} /></label>
        <label>VOLUME <input aria-label="App volume" type="range" min="0" max="1" step="0.01" value={lab.volume}
          onInput={(event) => this.commit({ ...lab, volume: Number(event.currentTarget.value) })} />
          <output>{Math.round(lab.volume * 100)}%</output></label>
        <label>INSTRUMENT <span class="instrument-color" style={{ background: lab.instruments.find((item) =>
          item.name === this.state.selectedInstrument)?.color }} /><select aria-label="Loop instrument"
          value={this.state.selectedInstrument} onChange={(event) => this.setState({ selectedInstrument: event.currentTarget.value })}>
          {lab.instruments.map((instrument) => <option value={instrument.name}>{instrument.name}</option>)}</select></label>
        <span role="status">{lab.instruments.some(hasPlayablePath) ? "SIGNAL READY" : "PATCH INCOMPLETE — SILENT"}</span></div>
      <div class="piano-scroll" tabIndex={0} aria-label="Scrollable two bar piano roll">
        <div class="piano-roll" role="grid" aria-label="Two bar piano roll"
          aria-rowcount={PITCHES.length} aria-colcount={32}>
        {PITCHES.map((pitch) => <div class={`pitch-row ${isNaturalPitch(pitch) ? "natural" : "sharp"}`} role="row">
          <span class="pitch-label">{midiLabel(pitch)}</span>
          {lab.notes.map((values, step) => {
            const assignments = values.filter((note) => note.pitch === pitch);
            const selected = assignments.find((note) => note.instrument === this.state.selectedInstrument);
            const color = lab.instruments.find((item) => item.name === (selected ?? assignments[0])?.instrument)?.color;
            return <button role="gridcell" class={`${assignments.length ? "active" : ""}
            ${this.state.activeStep === step ? "playing" : ""}
            ${step % 16 === 0 ? "bar" : step % 4 === 0 ? "beat" : ""}`}
            style={{ "--note-color": color }} aria-label={`${midiLabel(pitch)}, step ${step + 1}`}
            aria-pressed={Boolean(selected)} onClick={() => this.toggleNote(step, pitch)} />;
          })}</div>)}</div></div>
    </ConsolePane>;
  }
  override render() {
    const header = <UtilityRail><strong>WAVEFORM LAB</strong><span>MODULAR SIGNAL WORKBENCH</span>
      <span class="header-state">{this.state.playing ? "RUNNING" : "READY"}</span></UtilityRail>;
    const footer = <StatusRail><span>WEB AUDIO</span><span>13 MODULE TYPES · AUDIO + MODULATION</span></StatusRail>;
    return <ConsoleShell class="lab-shell" header={header} footer={footer}><ConsoleWorkspace class="workspace">
      <SynthYamlEditor lab={this.state.lab} commit={this.commit} />{this.renderSequencer()}
    </ConsoleWorkspace></ConsoleShell>;
  }
}

export function mount(root: HTMLElement): void { render(<WaveformLab />, root); }
