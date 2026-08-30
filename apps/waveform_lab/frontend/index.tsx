import { Component, render } from "preact";
import { ConsolePane, ConsoleShell, ConsoleWorkspace, StatusRail, UtilityRail } from "@xenorepo/ui";
import { SynthEngine } from "./audio.js";
import { decodeState, encodeState } from "./state-yaml.js";
import { SynthYamlEditor } from "./yaml-editor.js";
import {
  PITCHES, hasPlayablePath, initialState, midiLabel, type LabState,
} from "./model.js";
import "./styles.css";

const storageKey = "waveform-lab-state-v1";
interface ViewState { lab: LabState; playing: boolean; activeStep: number; }

function loadState(): LabState {
  const saved = localStorage.getItem(storageKey);
  if (!saved) return initialState();
  const restored = decodeState(saved);
  if (restored) return restored;
  localStorage.removeItem(storageKey); return initialState();
}

class WaveformLab extends Component<Record<string, never>, ViewState> {
  override state: ViewState = { lab: loadState(), playing: false, activeStep: -1 };
  private engine = new SynthEngine();

  override componentWillUnmount(): void { this.engine.stop(); }
  private commit = (lab: LabState): void => {
    this.engine.setVolume(lab.volume); this.setState({ lab }); localStorage.setItem(storageKey, encodeState(lab));
  };
  private togglePlayback = async (): Promise<void> => {
    if (this.state.playing) {
      this.engine.stop(); this.setState({ playing: false, activeStep: -1 }); return;
    }
    await this.engine.start(() => this.state.lab, (activeStep) => this.setState({ activeStep }));
    this.setState({ playing: true });
  };
  private toggleNote(step: number, pitch: number, hold: boolean): void {
    const lab = this.state.lab;
    if (hold) {
      const previous = (step + lab.holds.length - 1) % lab.holds.length;
      const anchored = lab.notes[previous]?.includes(pitch) || lab.holds[previous]?.includes(pitch);
      const holds = lab.holds.map((values) => [...values]);
      const current = holds[step] ?? [];
      if (current.includes(pitch)) holds[step] = current.filter((value) => value !== pitch);
      else if (anchored) holds[step] = [...current, pitch].sort((a, b) => a - b);
      this.commit({ ...lab, holds }); return;
    }
    const notes = lab.notes.map((values) => [...values]); const current = notes[step] ?? [];
    notes[step] = current.includes(pitch) ? current.filter((value) => value !== pitch)
      : [...current, pitch].sort((a, b) => a - b);
    const holds = lab.holds.map((values) => [...values]);
    if (current.includes(pitch)) {
      for (let index = (step + 1) % holds.length; holds[index]?.includes(pitch); index = (index + 1) % holds.length) {
        holds[index] = holds[index]?.filter((value) => value !== pitch) ?? [];
        if (index === step) break;
      }
    } else holds[step] = holds[step]?.filter((value) => value !== pitch) ?? [];
    this.commit({ ...lab, notes, holds });
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
        <span role="status">{hasPlayablePath(lab) ? "SIGNAL READY" : "PATCH INCOMPLETE — SILENT"}</span></div>
      <div class="piano-scroll" tabIndex={0} aria-label="Scrollable two bar piano roll">
        <div class="piano-roll" role="grid" aria-label="Two bar piano roll" aria-rowcount={24} aria-colcount={32}>
        {PITCHES.map((pitch) => <div class="pitch-row" role="row"><span class="pitch-label">{midiLabel(pitch)}</span>
          {lab.notes.map((values, step) => <button role="gridcell" class={`${values.includes(pitch) ? "active" : ""}
            ${lab.holds[step]?.includes(pitch) ? "held" : ""}
            ${this.state.activeStep === step ? "playing" : ""}
            ${step % 16 === 0 ? "bar" : step % 4 === 0 ? "beat" : ""}`}
            aria-label={`${midiLabel(pitch)}, step ${step + 1}`} aria-pressed={values.includes(pitch)}
            data-held={lab.holds[step]?.includes(pitch) ? "true" : undefined}
            onClick={(event) => this.toggleNote(step, pitch, event.shiftKey)} />)}</div>)}</div></div>
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
