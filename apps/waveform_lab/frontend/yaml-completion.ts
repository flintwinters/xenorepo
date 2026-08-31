import {
  autocompletion, type Completion, type CompletionContext, type CompletionResult,
} from "@codemirror/autocomplete";
import { stringify } from "yaml";
import { MODULE_REGISTRY, moduleDefinition, modulationTargets, type ModuleKind } from "./module-registry.js";
import { PRESET_CATALOG, presetInstrument } from "./presets.js";
import { instrumentMapOf } from "./state-yaml.js";

const kinds = Object.keys(MODULE_REGISTRY) as ModuleKind[];
const structural = [["color", "six-digit hex instrument color"], ["output", "reserved output settings"],
  ["modules", "instrument signal graph"], ["id", "unique module identifier"], ["kind", "module kind"],
  ["bypass", "disable an effect without rewiring"], ["connections", "outgoing connections"],
  ["from", "source module identifier"], ["to", "destination module identifier"],
  ["type", "audio or modulation connection"], ["target", "modulated parameter"],
  ["amount", "modulation depth in target units"]] as const;
const keys: Completion[] = structural.map(([label, detail]) =>
  ({ label, apply: `${label}: `, type: "property", detail }));

function nearestKind(context: CompletionContext): ModuleKind | null {
  const lines = context.state.sliceDoc(0, context.pos).split("\n");
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const kind = lines[index]?.match(/^\s+kind:\s*([\w-]+)/)?.[1] as ModuleKind | undefined;
    if (kind && kinds.includes(kind)) return kind;
    if (lines[index]?.match(/^\s*-\s+id:/)) return null;
  }
  return null;
}
function identifiers(context: CompletionContext): Completion[] {
  return [...context.state.doc.toString().matchAll(/^\s*-\s+id:\s*(\S+)/gm)]
    .map((match) => ({ label: match[1] as string, type: "variable", detail: "module id" }));
}
function presetOptions(context: CompletionContext): Completion[] {
  const source = context.state.doc.toString();
  return PRESET_CATALOG.map((preset) => ({ label: preset.name, type: "snippet", detail: preset.description,
    apply: (view, _completion, from, to) => { const base = preset.name; let name = base; let suffix = 2;
      while (new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}:`, "m").test(source))
        name = `${base}-${suffix++}`;
      const yaml = stringify(instrumentMapOf([presetInstrument(base, name)]), { lineWidth: 0 }).trimEnd();
      view.dispatch({ changes: { from, to, insert: yaml } }); } }));
}
function valueOptions(field: string, kind: ModuleKind | null, context: CompletionContext): Completion[] {
  if (field === "kind") return kinds.map((label) =>
    ({ label, type: "type", detail: MODULE_REGISTRY[label].description }));
  if (field === "type") return ["audio", "modulation"].map((label) => ({ label, type: "enum" }));
  if (field === "from" || field === "to") return identifiers(context);
  if (field === "target") return [...new Set(kinds.flatMap(modulationTargets))].sort()
    .map((label) => ({ label, type: "property", detail: "modulation target" }));
  const parameter = kind ? moduleDefinition(kind).parameters[field] : undefined;
  return parameter?.values?.map((label: string) => ({ label, type: "enum", detail: parameter.description })) ?? [];
}
function completions(context: CompletionContext): CompletionResult | null {
  const word = context.matchBefore(/[\w/-]*/); if (!word) return null;
  const line = context.state.doc.lineAt(context.pos); const prefix = line.text.slice(0, context.pos - line.from);
  if (!prefix.startsWith(" ") && /^(?:preset)?[\w -]*$/.test(prefix))
    return { from: prefix.startsWith("preset") ? line.from : word.from, options: presetOptions(context),
      validFor: /^(?:preset)?[\w /-]*$/, filter: false };
  if (!context.explicit && word.from === word.to) return null;
  const kind = nearestKind(context); const field = prefix.match(/(?:^|\s)([\w-]+):\s*[\w.-]*$/)?.[1];
  if (field) return { from: word.from, options: valueOptions(field, kind, context), validFor: /^[\w.-]*$/ };
  if (!/^\s*(?:-\s*)?[\w-]*$/.test(prefix)) return null;
  const parameters: Completion[] = kind ? Object.entries(MODULE_REGISTRY[kind].parameters).map(([label, definition]) =>
    ({ label, apply: `${label}: `, type: "property", detail: definition.range
      ? `${definition.description} (${definition.range[0]}–${definition.range[1]})` : definition.description })) : [];
  return { from: word.from, options: [...parameters, ...keys], validFor: /^[\w-]*$/ };
}
export const synthYamlCompletion = autocompletion({ override: [completions], activateOnTyping: true });
