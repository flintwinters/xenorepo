import { STEP_COUNT, type LabState, type SequencedNote } from "./model.js";

export interface Cell { step: number; pitch: number; }
export interface NoteOffset { step: number; pitch: number; }

export const cellKey = ({ step, pitch }: Cell): string => `${step}:${pitch}`;

export function selectionClass(selection: Set<string>, cell: Cell): string {
  if (!selection.has(cellKey(cell))) return "";
  const neighbors = {
    top: cell.pitch + 1, right: cell.step + 1,
    bottom: cell.pitch - 1, left: cell.step - 1,
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
  const highPitch = Math.max(start.pitch, end.pitch); const lowPitch = Math.min(start.pitch, end.pitch);
  const pitches = Array.from({ length: highPitch - lowPitch + 1 }, (_, index) => highPitch - index);
  return new Set(pitches.flatMap((pitch) =>
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
  const highestPitch = Math.max(...cells.map((cell) => cell.pitch));
  return cells.map((cell) => ({ step: cell.step - firstStep, pitch: highestPitch - cell.pitch }));
}

export function relativeOffsets(cells: Cell[], anchor: Cell): NoteOffset[] {
  return cells.map((cell) => ({ step: cell.step - anchor.step, pitch: anchor.pitch - cell.pitch }));
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
  const targets = clipboard.map((note) => ({ step: anchor.step + note.step,
    pitch: anchor.pitch - note.pitch })).filter((cell) =>
    cell.step >= 0 && cell.step < STEP_COUNT && Number.isSafeInteger(cell.pitch));
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
  const pitchDelta = destination.pitch - source.pitch;
  const targets = cells.map((cell) => ({ step: cell.step + stepDelta,
    pitch: cell.pitch + pitchDelta }));
  if (targets.some((cell) => cell.step < 0 || cell.step >= STEP_COUNT
    || !Number.isSafeInteger(cell.pitch))) return lab;
  const sourceRemoved = { ...lab, notes: withoutCells(lab, cells, instrument) };
  return pasteNotes(sourceRemoved, relativeOffsets(cells, source), destination, instrument);
}
