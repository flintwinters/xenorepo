import { Component, render } from "preact";
import {
  CommandButton, ConsolePane, ConsoleShell, ConsoleWorkspace, StatusRail, UtilityRail,
} from "@xenorepo/ui";
import { SynthEngine } from "./audio.js";
import { decodeState, encodeState } from "./state-yaml.js";
import { SynthYamlEditor } from "./yaml-editor.js";
import {
  initialState, isNaturalPitch, isSafeTopOctave, midiLabel, pitchesForTopOctave, type LabState,
} from "./model.js";
import {
  boxCells, cellKey, instrumentNotes, moveSelected, pasteNotes, relativeOffsets, removeSelected, selectedNotes,
  selectionClass, type Cell, type NoteOffset,
} from "./loop-selection.js";
import "./styles.css";

const storageKey = "waveform-lab-state-v1";
interface ViewState { lab: LabState; playing: boolean; activeStep: number; selectedInstrument: string;
  topOctave: number; selection: Set<string>; clipboard: NoteOffset[]; anchor: Cell | null; }

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
    selectedInstrument: this.initial.instruments[0]?.name ?? "", topOctave: 6,
    selection: new Set(), clipboard: [], anchor: null };
  private engine = new SynthEngine();
  private gesture: { start: Cell; mode: "box" | "move"; notes: Cell[] } | null = null;
  private dragged = false;

  override componentDidMount(): void { window.addEventListener("keydown", this.keyDown); }
  override componentWillUnmount(): void { this.engine.stop(); window.removeEventListener("keydown", this.keyDown); }
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
      : [...current, { pitch, instrument }]
        .sort((a, b) => a.pitch - b.pitch || a.instrument.localeCompare(b.instrument));
    this.commit({ ...this.state.lab, notes });
  }
  private select = (cell: Cell): void => {
    this.setState({ selection: new Set([cellKey(cell)]), anchor: cell });
  };
  private selectAll = (): void => {
    const notes = instrumentNotes(this.state.lab, this.state.selectedInstrument);
    if (!notes.length) return;
    this.setState({ selection: new Set(notes.map(cellKey)), anchor: notes[0] ?? null });
  };
  private copy = (): void => {
    const notes = selectedNotes(this.state.lab, this.state.selection, this.state.selectedInstrument);
    if (notes.length && this.state.anchor)
      this.setState({ clipboard: relativeOffsets(notes, this.state.anchor) });
  };
  private cut = (): void => { this.copy(); this.deleteSelection(); };
  private deleteSelection = (): void => {
    if (!this.state.selection.size) return;
    this.commit(removeSelected(this.state.lab, this.state.selection, this.state.selectedInstrument));
    this.setState({ selection: new Set() });
  };
  private paste = (): void => {
    if (!this.state.anchor || !this.state.clipboard.length) return;
    const lab = pasteNotes(this.state.lab, this.state.clipboard, this.state.anchor, this.state.selectedInstrument);
    const selection = new Set(this.state.clipboard.map((note) => cellKey({ step: this.state.anchor!.step + note.step,
      pitch: this.state.anchor!.pitch - note.pitch })));
    this.commit(lab); this.setState({ selection });
  };
  private keyDown = (event: KeyboardEvent): void => {
    const target = event.target as HTMLElement | null;
    if (target?.closest("input, select, textarea, [contenteditable=true], .cm-editor")) return;
    const modifier = event.ctrlKey || event.metaKey;
    const key = event.key.toLowerCase();
    if (modifier && key === "a") this.selectAll();
    else if (modifier && key === "c") this.copy();
    else if (modifier && key === "x") this.cut();
    else if (modifier && key === "v") this.paste();
    else if (!modifier && (event.key === "Delete" || event.key === "Backspace")) this.deleteSelection();
    else if (!modifier && event.key === "Escape") this.setState({ selection: new Set(), anchor: null });
    else if (!modifier && event.code === "Space") void this.togglePlayback();
    else return;
    event.preventDefault();
  };
  private pointerDown = (event: PointerEvent, cell: Cell): void => {
    if (event.button !== 0) return;
    const notes = selectedNotes(this.state.lab, this.state.selection, this.state.selectedInstrument);
    const active = notes.some((note) => cellKey(note) === cellKey(cell));
    this.gesture = { start: cell, mode: active ? "move" : "box", notes }; this.dragged = false;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  };
  private pointerMove = (event: PointerEvent): void => {
    if (!this.gesture || !(event.buttons & 1)) return;
    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>("[data-cell]");
    if (!target) return;
    const cell = { step: Number(target.dataset.step), pitch: Number(target.dataset.pitch) };
    if (cellKey(cell) === cellKey(this.gesture.start)) return;
    this.dragged = true;
    if (this.gesture.mode === "box")
      this.setState({ selection: boxCells(this.gesture.start, cell), anchor: this.gesture.start });
    else this.setState({ selection: new Set(this.gesture.notes.map((note) => cellKey(note))), anchor: cell });
  };
  private pointerUp = (event: PointerEvent): void => {
    if (!this.gesture) return;
    const gesture = this.gesture; this.gesture = null;
    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>("[data-cell]");
    const cell = target ? { step: Number(target.dataset.step), pitch: Number(target.dataset.pitch) } : gesture.start;
    if (this.dragged && gesture.mode === "move") {
      const lab = moveSelected(
        this.state.lab, gesture.notes, gesture.start, cell, this.state.selectedInstrument,
      );
      const moved = relativeOffsets(gesture.notes, gesture.start).map((note) => ({ step: cell.step + note.step,
        pitch: cell.pitch - note.pitch })).filter((note) =>
        note.step >= 0 && note.step < 32 && Number.isSafeInteger(note.pitch));
      this.commit(lab); this.setState({ selection: new Set(moved.map(cellKey)), anchor: cell });
    } else if (!this.dragged) { this.toggleNote(cell.step, cell.pitch); this.select(cell); }
  };
  private renderSequencer() {
    const lab = this.state.lab;
    const pitches = pitchesForTopOctave(this.state.topOctave);
    return <ConsolePane class="sequence-pane" title="LOOP / 2 BARS / 4∕4" tone="purple">
      <div class="transport"><CommandButton class="play" pressed={this.state.playing}
        onClick={this.togglePlayback}>{this.state.playing ? "■ STOP" : "▶ PLAY"}</CommandButton>
        <label>BPM <input aria-label="Tempo in BPM" type="number" min="40" max="240" value={lab.bpm}
          onChange={(event) => this.commit({ ...lab,
            bpm: Math.max(40, Math.min(240, Number(event.currentTarget.value) || 120)),
          })} /></label>
        <label>VOLUME <input aria-label="App volume" type="range" min="0" max="1" step="0.01" value={lab.volume}
          onInput={(event) => this.commit({ ...lab, volume: Number(event.currentTarget.value) })} />
          <output>{Math.round(lab.volume * 100)}%</output></label>
        <label>INSTRUMENT <span class="instrument-color" style={{ background: lab.instruments.find((item) =>
          item.name === this.state.selectedInstrument)?.color }} /><select aria-label="Loop instrument"
          value={this.state.selectedInstrument}
          onChange={(event) => this.setState({ selectedInstrument: event.currentTarget.value })}>
          {lab.instruments.map((instrument) => <option value={instrument.name}>
            {instrument.name}</option>)}</select></label>
        <label>TOP OCTAVE <input aria-label="Highest visible octave" type="number" value={this.state.topOctave}
          onChange={(event) => { const octave = Number(event.currentTarget.value);
            if (isSafeTopOctave(octave)) this.setState({ topOctave: octave, selection: new Set(), anchor: null });
          }} /></label>
        <div class="selection-tools" aria-label="Note selection controls"
          title="Ctrl/Cmd+A select all · Ctrl/Cmd+X/C/V cut/copy/paste · Backspace/Delete remove · Esc clear · Space play">
          <CommandButton onClick={this.cut}
          disabled={!this.state.selection.size}>CUT</CommandButton><CommandButton onClick={this.copy}
            disabled={!this.state.selection.size}>COPY</CommandButton>
          <CommandButton onClick={this.paste}
            disabled={!this.state.clipboard.length || !this.state.anchor}>PASTE</CommandButton>
          <CommandButton onClick={this.deleteSelection}
            disabled={!this.state.selection.size}>DELETE</CommandButton>
          <output>{this.state.selection.size} SELECTED</output></div></div>
      <div class="piano-scroll" tabIndex={0} aria-label="Two bar piano roll editor">
        <div class="piano-roll" role="grid" aria-label="Two bar piano roll"
          aria-rowcount={pitches.length} aria-colcount={32}>
        {pitches.map((pitch) => <div class={`pitch-row ${isNaturalPitch(pitch) ? "natural" : "sharp"}`} role="row">
          <span class="pitch-label">{midiLabel(pitch)}</span>
          {lab.notes.map((values, step) => {
            const assignments = values.filter((note) => note.pitch === pitch);
            const selected = assignments.find((note) => note.instrument === this.state.selectedInstrument);
            const color = lab.instruments.find((item) => item.name === (selected ?? assignments[0])?.instrument)?.color;
            return <button role="gridcell" class={`note-cell ${assignments.length ? "active" : ""}
            ${selectionClass(this.state.selection, { step, pitch })}
            ${this.state.activeStep === step ? "playing" : ""}
            ${step % 16 === 0 ? "bar" : step % 4 === 0 ? "beat" : ""}`}
            data-cell data-step={step} data-pitch={pitch}
            style={{ "--note-color": color }} aria-label={`${midiLabel(pitch)}, step ${step + 1}`}
            aria-pressed={Boolean(selected)} onDblClick={() => this.toggleNote(step, pitch)}
            onPointerDown={(event) => this.pointerDown(event, { step, pitch })}
            onPointerMove={this.pointerMove} onPointerUp={this.pointerUp} />;
          })}</div>)}</div></div>
    </ConsolePane>;
  }
  override render() {
    const header = <UtilityRail><strong>WAVEFORM LAB</strong><span>MODULAR SIGNAL WORKBENCH</span>
      <span class="header-state">{this.state.playing ? "RUNNING" : "READY"}</span></UtilityRail>;
    const footer = <StatusRail><span>WEB AUDIO</span><span>16 MODULE TYPES · AUDIO + MODULATION</span></StatusRail>;
    return <ConsoleShell class="lab-shell" header={header} footer={footer}><ConsoleWorkspace class="workspace">
      <SynthYamlEditor lab={this.state.lab} commit={this.commit} />{this.renderSequencer()}
    </ConsoleWorkspace></ConsoleShell>;
  }
}

export function mount(root: HTMLElement): void { render(<WaveformLab />, root); }
