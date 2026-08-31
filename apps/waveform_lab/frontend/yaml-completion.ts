import {
  autocompletion, type Completion, type CompletionContext, type CompletionResult,
} from "@codemirror/autocomplete";
import { MODULATION_TARGETS, PARAMETER_BOUNDS, type ModuleKind } from "./model.js";

const moduleKinds = Object.keys(PARAMETER_BOUNDS) as ModuleKind[];
const valueOptions: Readonly<Record<string, Completion[]>> = {
  kind: moduleKinds.map((label) => ({ label, type: "type", detail: "module kind" })),
  waveform: ["sine", "square", "saw", "triangle"]
    .map((label) => ({ label, type: "enum", detail: "oscillator waveform" })),
  type: ["audio", "modulation"].map((label) => ({ label, type: "enum", detail: "connection type" })),
  mode: [
    { label: "0", type: "enum", detail: "low-pass" },
    { label: "1", type: "enum", detail: "high-pass" },
    { label: "2", type: "enum", detail: "band-pass" },
    { label: "3", type: "enum", detail: "notch" },
  ],
};

const structuralFields: ReadonlyArray<readonly [string, string]> = [
  ["color", "six-digit hex instrument color"], ["waveform", "instrument oscillator shape"],
  ["output", "reserved output settings"], ["modules", "instrument signal graph"],
  ["id", "unique module identifier"], ["kind", "available module kind"],
  ["bypass", "disable an effect without rewiring"], ["connections", "outgoing signal connections"],
  ["from", "source module identifier"], ["to", "destination module identifier"],
  ["type", "audio or modulation connection"], ["target", "modulated parameter"],
];
const structuralKeys: Completion[] = structuralFields
  .map(([label, detail]) => ({ label, apply: `${label}: `, type: "property", detail }));

function nearestModuleKind(context: CompletionContext): ModuleKind | null {
  const lines = context.state.sliceDoc(0, context.pos).split("\n");
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const id = lines[index]?.match(/^\s*-\s+id:/);
    const kind = lines[index]?.match(/^\s+kind:\s*([\w-]+)/)?.[1] as ModuleKind | undefined;
    if (kind && moduleKinds.includes(kind)) return kind;
    if (id) return null;
  }
  return null;
}

function identifiers(context: CompletionContext): Completion[] {
  return [...context.state.doc.toString().matchAll(/^\s*-\s+id:\s*(\S+)/gm)]
    .map((match) => ({ label: match[1] as string, type: "variable", detail: "module id" }));
}

function targetOptions(): Completion[] {
  return [...new Set(Object.values(MODULATION_TARGETS).flatMap((names) => names ?? []))]
    .sort().map((label) => ({ label, type: "property", detail: "modulation target" }));
}

function synthCompletions(context: CompletionContext): CompletionResult | null {
  const word = context.matchBefore(/[\w-]*/);
  if (!word || (!context.explicit && word.from === word.to)) return null;
  const line = context.state.doc.lineAt(context.pos);
  const prefix = line.text.slice(0, context.pos - line.from);
  const value = prefix.match(/(?:^|\s)(kind|waveform|type|target|mode|from|to):\s*[\w-]*$/)?.[1];
  if (value) {
    const options = value === "target" ? targetOptions()
      : value === "from" || value === "to" ? identifiers(context) : valueOptions[value] ?? [];
    return { from: word.from, options, validFor: /^[\w-]*$/ };
  }
  if (!/^\s*(?:-\s*)?[\w-]*$/.test(prefix)) return null;
  const kind = nearestModuleKind(context);
  const parameterKeys = kind ? Object.keys(PARAMETER_BOUNDS[kind]).map((label) => ({
    label, apply: `${label}: `, type: "property", detail: `${kind} parameter`,
  })) : [];
  return { from: word.from, options: [...parameterKeys, ...structuralKeys], validFor: /^[\w-]*$/ };
}

export const synthYamlCompletion = autocompletion({ override: [synthCompletions], activateOnTyping: true });
