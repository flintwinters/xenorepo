import { Component, render } from "preact";
import { CommandButton, ConsolePane, ConsoleShell, StatusRail, UtilityRail } from "@xenorepo/ui";
import { SynthEngine } from "./audio.js";
import { CircuitPanel } from "./circuit.js";
import {
  PITCHES,
  SAMPLE_COUNT,
  drawSamples,
  hasPlayablePath,
  initialState,
  midiLabel,
  preset,
  restoreState,
  type LabState,
} from "./model.js";
import "./styles.css";

const storageKey = "waveform-lab-state-v1";
interface ViewState {
  lab: LabState;
  playing: boolean;
  activeStep: number;
  history: number[][];
}

function loadState(): LabState {
  try {
    return restoreState(JSON.parse(localStorage.getItem(storageKey) ?? "null"));
  } catch {
    localStorage.removeItem(storageKey);
    return initialState();
  }
}

class WaveformLab extends Component<Record<string, never>, ViewState> {
  override state: ViewState = { lab: loadState(), playing: false, activeStep: -1, history: [] };
  private engine = new SynthEngine();
  private lastPoint: [number, number] | null = null;

  override componentWillUnmount(): void {
    this.engine.stop();
  }
  private commit = (lab: LabState): void => {
    this.setState({ lab });
    localStorage.setItem(storageKey, JSON.stringify(lab));
  };
  private togglePlayback = async (): Promise<void> => {
    if (this.state.playing) {
      this.engine.stop();
      this.setState({ playing: false, activeStep: -1 });
      return;
    }
    await this.engine.start(
      () => this.state.lab,
      (activeStep) => this.setState({ activeStep }),
    );
    this.setState({ playing: true });
  };
  private waveformPoint(event: PointerEvent): [number, number] {
    const bounds = (event.currentTarget as SVGSVGElement).getBoundingClientRect();
    return [
      Math.max(0, Math.min(SAMPLE_COUNT - 1, ((event.clientX - bounds.left) / bounds.width) * (SAMPLE_COUNT - 1))),
      Math.max(-1, Math.min(1, 1 - ((event.clientY - bounds.top) / bounds.height) * 2)),
    ];
  }
  private beginWave = (event: PointerEvent): void => {
    this.lastPoint = this.waveformPoint(event);
    this.setState({ history: [...this.state.history.slice(-19), this.state.lab.samples] });
    try {
      (event.currentTarget as SVGSVGElement).setPointerCapture(event.pointerId);
    } catch {
      /* Synthetic pointer. */
    }
    this.commit({ ...this.state.lab, samples: drawSamples(this.state.lab.samples, this.lastPoint, this.lastPoint) });
  };
  private drawWave = (event: PointerEvent): void => {
    if (!this.lastPoint || event.buttons === 0) return;
    const point = this.waveformPoint(event);
    this.commit({ ...this.state.lab, samples: drawSamples(this.state.lab.samples, this.lastPoint, point) });
    this.lastPoint = point;
  };
  private endWave = (): void => {
    this.lastPoint = null;
  };
  private applyPreset(kind: "sine" | "square" | "saw" | "triangle"): void {
    this.setState({ history: [...this.state.history.slice(-19), this.state.lab.samples] });
    this.commit({ ...this.state.lab, samples: preset(kind) });
  }
  private undoWave(): void {
    const samples = this.state.history.at(-1);
    if (!samples) return;
    this.commit({ ...this.state.lab, samples });
    this.setState({ history: this.state.history.slice(0, -1) });
  }
  private toggleNote(step: number, pitch: number, hold: boolean): void {
    const lab = this.state.lab;
    if (hold) {
      const previous = (step + lab.holds.length - 1) % lab.holds.length;
      const anchored = lab.notes[previous]?.includes(pitch) || lab.holds[previous]?.includes(pitch);
      const holds = lab.holds.map((values) => [...values]);
      const current = holds[step] ?? [];
      if (current.includes(pitch)) {
        for (let index = step; holds[index]?.includes(pitch); index = (index + 1) % holds.length) {
          holds[index] = holds[index]?.filter((value) => value !== pitch) ?? [];
          if (index === (step + holds.length - 1) % holds.length) break;
        }
      } else if (anchored) holds[step] = [...current, pitch].sort((a, b) => a - b);
      this.commit({ ...lab, holds });
      return;
    }
    const notes = lab.notes.map((values) => [...values]);
    const current = notes[step] ?? [];
    notes[step] = current.includes(pitch)
      ? current.filter((value) => value !== pitch)
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
  private renderWaveform() {
    const points = this.state.lab.samples
      .map((sample, index) => `${(index / (SAMPLE_COUNT - 1)) * 1000},${(1 - sample) * 110}`)
      .join(" ");
    return (
      <ConsolePane class="wave-pane" title="WAVEFORM / SINGLE CYCLE" tone="green">
        <div class="wave-tools">
          {(["sine", "square", "saw", "triangle"] as const).map((kind) => (
            <CommandButton onClick={() => this.applyPreset(kind)}>{kind}</CommandButton>
          ))}
          <CommandButton disabled={!this.state.history.length} onClick={() => this.undoWave()}>
            undo
          </CommandButton>
          <CommandButton
            onClick={() => {
              this.setState({ history: [] });
              this.commit({ ...this.state.lab, samples: preset("sine") });
            }}
          >
            reset
          </CommandButton>
        </div>
        <svg
          class="wave-editor"
          viewBox="0 0 1000 220"
          preserveAspectRatio="none"
          role="img"
          aria-label="Draw one cycle waveform"
          onPointerDown={this.beginWave}
          onPointerMove={this.drawWave}
          onPointerUp={this.endWave}
          onPointerCancel={this.endWave}
        >
          <path class="wave-grid" d="M0 55H1000 M0 110H1000 M0 165H1000 M250 0V220 M500 0V220 M750 0V220" />
          <polyline points={points} />
        </svg>
        <p class="editor-note">128 SAMPLE FUNCTION · −1…+1 · DRAW HORIZONTALLY</p>
      </ConsolePane>
    );
  }
  private renderSequencer() {
    const lab = this.state.lab;
    return (
      <ConsolePane class="sequence-pane" title="LOOP / 2 BARS / 4∕4" tone="purple" contentHeight>
        <div class="transport">
          <CommandButton class="play" aria-pressed={this.state.playing} onClick={this.togglePlayback}>
            {this.state.playing ? "■ STOP" : "▶ PLAY"}
          </CommandButton>
          <label>
            BPM{" "}
            <input
              aria-label="Tempo in BPM"
              type="number"
              min="40"
              max="240"
              value={lab.bpm}
              onChange={(event) => this.commit({
                ...lab,
                bpm: Math.max(40, Math.min(240, Number(event.currentTarget.value) || 120)),
              })}
            />
          </label>
            <span role="status">
              {hasPlayablePath(lab) ? "SIGNAL READY" : "PATCH INCOMPLETE — SILENT"}
            </span>
        </div>
        <div class="piano-scroll" tabIndex={0} aria-label="Scrollable two bar piano roll">
          <div class="piano-roll" role="grid" aria-label="Two bar piano roll" aria-rowcount={24} aria-colcount={32}>
            {PITCHES.map((pitch) => (
              <div class="pitch-row" role="row">
                <span class="pitch-label">{midiLabel(pitch)}</span>
                {lab.notes.map((values, step) => (
                  <button
                    data-ui-control="domain"
                    role="gridcell"
                    class={`${values.includes(pitch) ? "active" : ""}
            ${lab.holds[step]?.includes(pitch) ? "held" : ""}
            ${this.state.activeStep === step ? "playing" : ""} ${step % 16 === 0 ? "bar" : step % 4 === 0 ? "beat" : ""}`}
                    aria-label={`${midiLabel(pitch)}, step ${step + 1}`}
                    aria-pressed={values.includes(pitch)}
                    data-held={lab.holds[step]?.includes(pitch) ? "true" : undefined}
                    onClick={(event) => this.toggleNote(step, pitch, event.shiftKey)}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
        <p class="editor-note">CLICK: TOGGLE NOTE · SHIFT+CLICK: HOLD FROM PREVIOUS STEP</p>
      </ConsolePane>
    );
  }
  override render() {
    const header = (
      <UtilityRail>
        <strong>WAVEFORM LAB</strong>
        <span>MODULAR SIGNAL WORKBENCH</span>
        <span class="header-state">{this.state.playing ? "RUNNING" : "READY"}</span>
      </UtilityRail>
    );
    const footer = (
      <StatusRail>
        <span>WEB AUDIO</span>
        <span>13 MODULE TYPES · AUDIO + MODULATION</span>
      </StatusRail>
    );
    return (
      <ConsoleShell class="lab-shell" header={header} footer={footer}>
        <div class="workspace">
          <CircuitPanel lab={this.state.lab} commit={this.commit} />
          {this.renderWaveform()}
          {this.renderSequencer()}
        </div>
      </ConsoleShell>
    );
  }
}

export function mount(root: HTMLElement): void {
  render(<WaveformLab />, root);
}
