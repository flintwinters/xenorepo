import { PITCHES, STEP_COUNT, type LabState, type SequencedNote } from "./model.js";

export interface Cell { step: number; pitch: number; }
export interface NoteOffset { step: number; pitch: number; }

export const cellKey = ({ step, pitch }: Cell): string => `${step}:${pitch}`;

export function selectionClass(selection: Set<string>, cell: Cell): string {
  if (!selection.has(cellKey(cell))) return "";
  const row = PITCHES.indexOf(cell.pitch);
  const neighbors = {
    top: PITCHES[row - 1], right: cell.step + 1,
    bottom: PITCHES[row + 1], left: cell.step - 1,
  };
  const edges = [
    !selection.has(cellKey({ step: cell.step, pitch: neighbors.top ?? -1 })) && "selection-top",
    !selection.has(cellKey({ step: neighbors.right, pitch: cell.pitch })) && "selection-right",
    !selection.has(cellKey({ step: cell.step, pitch: neighbors.bottom ?? -1 })) && "selection-bottom",
    !selection.has(cellKey({ step: neighbors.left, pitch: cell.pitch })) && "selection-left",
  ];
  return ["selected", ...edges.filter(Boolean)].join(" ");
}

export function boxCells(start: Cell, end: Cell): Set<string> {
  const lowStep = Math.min(start.step, end.step); const highStep = Math.max(start.step, end.step);
  const startRow = PITCHES.indexOf(start.pitch); const endRow = PITCHES.indexOf(end.pitch);
  const lowRow = Math.min(startRow, endRow); const highRow = Math.max(startRow, endRow);
  return new Set(PITCHES.slice(lowRow, highRow + 1).flatMap((pitch) =>
    Array.from({ length: highStep - lowStep + 1 }, (_, index) => cellKey({ step: lowStep + index, pitch }))));
}

export function selectedNotes(lab: LabState, selection: Set<string>, instrument: string): Cell[] {
  return lab.notes.flatMap((notes, step) => notes
    .filter((note) => note.instrument === instrument && selection.has(cellKey({ step, pitch: note.pitch })))
    .map((note) => ({ step, pitch: note.pitch })));
}

export function offsets(cells: Cell[]): NoteOffset[] {
  if (!cells.length) return [];
  const firstStep = Math.min(...cells.map((cell) => cell.step));
  const firstRow = Math.min(...cells.map((cell) => PITCHES.indexOf(cell.pitch)));
  return cells.map((cell) => ({ step: cell.step - firstStep, pitch: PITCHES.indexOf(cell.pitch) - firstRow }));
}

export function relativeOffsets(cells: Cell[], anchor: Cell): NoteOffset[] {
  const anchorRow = PITCHES.indexOf(anchor.pitch);
  return cells.map((cell) => ({ step: cell.step - anchor.step, pitch: PITCHES.indexOf(cell.pitch) - anchorRow }));
}

function withoutCells(lab: LabState, cells: Cell[], instrument: string): SequencedNote[][] {
  const removed = new Set(cells.map(cellKey));
  return lab.notes.map((notes, step) => notes.filter((note) =>
    note.instrument !== instrument || !removed.has(cellKey({ step, pitch: note.pitch }))));
}

export function removeSelected(lab: LabState, selection: Set<string>, instrument: string): LabState {
  return { ...lab, notes: withoutCells(lab, selectedNotes(lab, selection, instrument), instrument) };
}

export function pasteNotes(lab: LabState, clipboard: NoteOffset[], anchor: Cell, instrument: string): LabState {
  const anchorRow = PITCHES.indexOf(anchor.pitch);
  const targets = clipboard.map((note) => ({ step: anchor.step + note.step,
    pitch: PITCHES[anchorRow + note.pitch] })).filter((cell): cell is Cell =>
    cell.step >= 0 && cell.step < STEP_COUNT && typeof cell.pitch === "number");
  const notes = lab.notes.map((values) => [...values]);
  for (const target of targets) {
    const values = notes[target.step] ?? [];
    if (!values.some((note) => note.pitch === target.pitch && note.instrument === instrument))
      notes[target.step] = [...values, { pitch: target.pitch, instrument }]
        .sort((a, b) => a.pitch - b.pitch || a.instrument.localeCompare(b.instrument));
  }
  return { ...lab, notes };
}

export function moveSelected(
  lab: LabState, cells: Cell[], source: Cell, destination: Cell, instrument: string,
): LabState {
  if (!cells.length) return lab;
  const stepDelta = destination.step - source.step;
  const rowDelta = PITCHES.indexOf(destination.pitch) - PITCHES.indexOf(source.pitch);
  const targets = cells.map((cell) => ({ step: cell.step + stepDelta,
    pitch: PITCHES[PITCHES.indexOf(cell.pitch) + rowDelta] }));
  if (targets.some((cell) => cell.step < 0 || cell.step >= STEP_COUNT
    || typeof cell.pitch !== "number")) return lab;
  const sourceRemoved = { ...lab, notes: withoutCells(lab, cells, instrument) };
  return pasteNotes(sourceRemoved, relativeOffsets(cells, source), destination, instrument);
}
