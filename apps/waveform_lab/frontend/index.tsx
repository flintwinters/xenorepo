import { Component, render } from "preact";
import { ConsolePane, ConsoleShell, StatusRail, UtilityRail } from "@xenorepo/ui";
import { SynthEngine } from "./audio.js";
import {
  PITCHES, SAMPLE_COUNT, drawSamples, hasPlayablePath, initialState, midiLabel, preset,
  restoreState, validConnection, type LabState, type ModuleKind,
} from "./model.js";
import "./styles.css";

const storageKey = "waveform-lab-state-v1";
type Drag = { id: string; dx: number; dy: number; pointerId: number };
interface ViewState { lab: LabState; playing: boolean; activeStep: number; pendingOutput: string | null; history: number[][]; }

function loadState(): LabState {
  try { return restoreState(JSON.parse(localStorage.getItem(storageKey) ?? "null")); }
  catch { localStorage.removeItem(storageKey); return initialState(); }
}

class WaveformLab extends Component<Record<string, never>, ViewState> {
  override state: ViewState = { lab: loadState(), playing: false, activeStep: -1, pendingOutput: null, history: [] };
  private engine = new SynthEngine();
  private drag: Drag | null = null;
  private lastPoint: [number, number] | null = null;

  override componentWillUnmount(): void { this.engine.stop(); }
  private commit(lab: LabState): void { this.setState({ lab }); localStorage.setItem(storageKey, JSON.stringify(lab)); }

  private togglePlayback = async (): Promise<void> => {
    if (this.state.playing) {
      this.engine.stop(); this.setState({ playing: false, activeStep: -1 }); return;
    }
    await this.engine.start(() => this.state.lab, (activeStep) => this.setState({ activeStep }));
    this.setState({ playing: true });
  };

  private addModule(kind: ModuleKind): void {
    const count = this.state.lab.modules.filter((node) => node.kind === kind).length + 1;
    const node = { id: `${kind}-${crypto.randomUUID()}`, kind, x: 40 + count * 34, y: 50 + count * 28 };
    this.commit({ ...this.state.lab, modules: [...this.state.lab.modules, node] });
  }

  private removeModule(id: string): void {
    const lab = this.state.lab;
    this.commit({ ...lab, modules: lab.modules.filter((node) => node.id !== id),
      connections: lab.connections.filter((edge) => edge.from !== id && edge.to !== id) });
    if (this.state.pendingOutput === id) this.setState({ pendingOutput: null });
  }

  private choosePort(id: string, direction: "input" | "output"): void {
    if (direction === "output") { this.setState({ pendingOutput: this.state.pendingOutput === id ? null : id }); return; }
    const from = this.state.pendingOutput;
    if (!from) return;
    const connection = { from, to: id };
    const lab = this.state.lab;
    if (validConnection(lab.modules, connection)
      && !lab.connections.some((edge) => edge.from === from && edge.to === id))
      this.commit({ ...lab, connections: [...lab.connections, connection] });
    this.setState({ pendingOutput: null });
  }

  private startDrag(event: PointerEvent, id: string): void {
    if ((event.target as HTMLElement).closest("button")) return;
    const node = this.state.lab.modules.find((item) => item.id === id);
    if (!node) return;
    const circuit = (event.currentTarget as HTMLElement).parentElement?.getBoundingClientRect();
    if (!circuit) return;
    this.drag = { id, dx: event.clientX - circuit.left - node.x,
      dy: event.clientY - circuit.top - node.y, pointerId: event.pointerId };
    try { (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId); } catch { /* Synthetic pointer. */ }
  }

  private moveModule = (event: PointerEvent): void => {
    if (!this.drag || this.drag.pointerId !== event.pointerId) return;
    const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const modules = this.state.lab.modules.map((node) => node.id === this.drag?.id
      ? { ...node, x: Math.max(0, Math.min(bounds.width - 152, event.clientX - bounds.left - this.drag.dx)),
        y: Math.max(0, Math.min(bounds.height - 92, event.clientY - bounds.top - this.drag.dy)) } : node);
    this.setState({ lab: { ...this.state.lab, modules } });
  };
  private endDrag = (): void => { if (this.drag) this.commit(this.state.lab); this.drag = null; };

  private waveformPoint(event: PointerEvent): [number, number] {
    const bounds = (event.currentTarget as SVGSVGElement).getBoundingClientRect();
    const x = Math.max(0, Math.min(SAMPLE_COUNT - 1,
      (event.clientX - bounds.left) / bounds.width * (SAMPLE_COUNT - 1)));
    const y = Math.max(-1, Math.min(1, 1 - (event.clientY - bounds.top) / bounds.height * 2));
    return [x, y];
  }

  private beginWave = (event: PointerEvent): void => {
    this.lastPoint = this.waveformPoint(event);
    this.setState({ history: [...this.state.history.slice(-19), this.state.lab.samples] });
    try { (event.currentTarget as SVGSVGElement).setPointerCapture(event.pointerId); } catch { /* Synthetic pointer. */ }
    this.commit({ ...this.state.lab, samples: drawSamples(this.state.lab.samples, this.lastPoint, this.lastPoint) });
  };
  private drawWave = (event: PointerEvent): void => {
    if (!this.lastPoint || event.buttons === 0) return;
    const point = this.waveformPoint(event);
    this.commit({ ...this.state.lab, samples: drawSamples(this.state.lab.samples, this.lastPoint, point) });
    this.lastPoint = point;
  };
  private endWave = (): void => { this.lastPoint = null; };

  private applyPreset(kind: "sine" | "square" | "saw" | "triangle"): void {
    this.setState({ history: [...this.state.history.slice(-19), this.state.lab.samples] });
    this.commit({ ...this.state.lab, samples: preset(kind) });
  }
  private undoWave(): void {
    const samples = this.state.history.at(-1);
    if (!samples) return;
    this.commit({ ...this.state.lab, samples }); this.setState({ history: this.state.history.slice(0, -1) });
  }
  private toggleNote(step: number, pitch: number): void {
    const notes = this.state.lab.notes.map((values) => [...values]);
    const current = notes[step] ?? [];
    notes[step] = current.includes(pitch)
      ? current.filter((value) => value !== pitch) : [...current, pitch].sort((a, b) => a - b);
    this.commit({ ...this.state.lab, notes });
  }

  private renderCircuit() {
    const lab = this.state.lab;
    return <ConsolePane class="circuit-pane" title="PATCH BAY" tone="orange">
      <div class="module-tools" aria-label="Add circuit module">
        {(["waveform", "gain", "output"] as const).map((kind) =>
          <button onClick={() => this.addModule(kind)}>+ {kind.toUpperCase()}</button>)}
      </div>
      <div class="circuit" onPointerMove={this.moveModule} onPointerUp={this.endDrag} onPointerCancel={this.endDrag}>
        <svg class="cables" aria-hidden="true">{lab.connections.map((edge) => {
          const from = lab.modules.find((node) => node.id === edge.from);
          const to = lab.modules.find((node) => node.id === edge.to);
          return from && to ? <line x1={from.x + 152} y1={from.y + 46} x2={to.x} y2={to.y + 46} /> : null;
        })}</svg>
        {lab.modules.map((node) => <article class={`module ${node.kind}`} style={{ left: node.x, top: node.y }}
          onPointerDown={(event) => this.startDrag(event, node.id)}>
          <header><strong>{node.kind.toUpperCase()}</strong><button aria-label={`Remove ${node.kind} module`}
            onClick={() => this.removeModule(node.id)}>×</button></header>
          {node.kind !== "waveform" && <button class="port input" aria-label={`Connect input of ${node.id}`}
            onClick={() => this.choosePort(node.id, "input")}>IN</button>}
          {node.kind !== "output" && <button class={`port output ${this.state.pendingOutput === node.id ? "armed" : ""}`}
            aria-label={`Connect output of ${node.id}`} onClick={() => this.choosePort(node.id, "output")}>OUT</button>}
          <span class="module-id">{node.id}</span>
        </article>)}
      </div>
      <ol class="connections" aria-label="Connections">{lab.connections.map((edge) => <li>{edge.from} → {edge.to}
        <button aria-label={`Disconnect ${edge.from} from ${edge.to}`} onClick={() => this.commit({ ...lab,
          connections: lab.connections.filter((item) => item !== edge) })}>disconnect</button></li>)}</ol>
    </ConsolePane>;
  }

  private renderWaveform() {
    const points = this.state.lab.samples.map((sample, index) =>
      `${index / (SAMPLE_COUNT - 1) * 1000},${(1 - sample) * 110}`).join(" ");
    return <ConsolePane class="wave-pane" title="WAVEFORM / SINGLE CYCLE" tone="green">
      <div class="wave-tools">{(["sine", "square", "saw", "triangle"] as const).map((kind) =>
        <button onClick={() => this.applyPreset(kind)}>{kind}</button>)}
        <button disabled={!this.state.history.length} onClick={() => this.undoWave()}>undo</button>
        <button onClick={() => { this.setState({ history: [] }); this.commit({ ...this.state.lab, samples: preset("sine") }); }}>reset</button>
      </div>
      <svg class="wave-editor" viewBox="0 0 1000 220" preserveAspectRatio="none" role="img"
        aria-label="Draw one cycle waveform" onPointerDown={this.beginWave} onPointerMove={this.drawWave}
        onPointerUp={this.endWave} onPointerCancel={this.endWave}>
        <path class="wave-grid" d="M0 55H1000 M0 110H1000 M0 165H1000 M250 0V220 M500 0V220 M750 0V220" />
        <polyline points={points} />
      </svg><p class="editor-note">128 SAMPLE FUNCTION · −1…+1 · DRAW HORIZONTALLY</p>
    </ConsolePane>;
  }

  private renderSequencer() {
    const lab = this.state.lab;
    return <ConsolePane class="sequence-pane" title="LOOP / 2 BARS / 4∕4" tone="purple">
      <div class="transport"><button class="play" aria-pressed={this.state.playing} onClick={this.togglePlayback}>
        {this.state.playing ? "■ STOP" : "▶ PLAY"}</button>
        <label>BPM <input aria-label="Tempo in BPM" type="number" min="40" max="240" value={lab.bpm}
          onChange={(event) => this.commit({ ...lab, bpm: Math.max(40, Math.min(240, Number(event.currentTarget.value) || 120)) })} /></label>
        <span>{hasPlayablePath(lab) ? "SIGNAL READY" : "PATCH INCOMPLETE — SILENT"}</span></div>
      <div class="piano-scroll"><div class="piano-roll" role="grid" aria-label="Two bar piano roll">
        {PITCHES.map((pitch) => <div class="pitch-row" role="row"><span class="pitch-label">{midiLabel(pitch)}</span>
          {lab.notes.map((values, step) => <button role="gridcell" class={`${values.includes(pitch) ? "active" : ""}
            ${this.state.activeStep === step ? "playing" : ""} ${step % 16 === 0 ? "bar" : step % 4 === 0 ? "beat" : ""}`}
            aria-label={`${midiLabel(pitch)}, step ${step + 1}`} aria-pressed={values.includes(pitch)}
            onClick={() => this.toggleNote(step, pitch)} />)}</div>)}
      </div></div>
    </ConsolePane>;
  }

  override render() {
    const header = <UtilityRail><strong>WAVEFORM LAB</strong><span>MODULAR SIGNAL WORKBENCH</span>
      <span class="header-state">{this.state.playing ? "RUNNING" : "READY"}</span></UtilityRail>;
    const footer = <StatusRail><span>WEB AUDIO</span><span>LOCAL PATCH · C4–B5 · 32 STEPS</span></StatusRail>;
    return <ConsoleShell class="lab-shell" header={header} footer={footer}><div class="workspace">
      {this.renderCircuit()} {this.renderWaveform()} {this.renderSequencer()}
    </div></ConsoleShell>;
  }
}

export function mount(root: HTMLElement): void { render(<WaveformLab />, root); }
