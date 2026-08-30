import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorView } from "@codemirror/view";
import { tags } from "@lezer/highlight";

const background = "#282828";
const backgroundHard = "#1d2021";
const backgroundSoft = "#32302f";
const foreground = "#ebdbb2";
const gray = "#928374";
const yellow = "#fabd2f";
const orange = "#fe8019";
const red = "#fb4934";
const green = "#b8bb26";
const aqua = "#8ec07c";
const blue = "#83a598";
const purple = "#d3869b";

const editorTheme = EditorView.theme({
  "&": { color: foreground, backgroundColor: background },
  ".cm-content": { caretColor: yellow },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: yellow },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {
    backgroundColor: "#504945",
  },
  ".cm-activeLine": { backgroundColor: backgroundSoft },
  ".cm-gutters": { color: gray, backgroundColor: backgroundHard, borderRightColor: "#3c3836" },
  ".cm-activeLineGutter": { color: yellow, backgroundColor: backgroundSoft },
  ".cm-foldPlaceholder": { color: foreground, backgroundColor: "#504945", borderColor: gray },
  ".cm-panels": { color: foreground, backgroundColor: backgroundHard },
  ".cm-panels.cm-panels-top": { borderBottomColor: "#504945" },
  ".cm-textfield": { color: foreground, backgroundColor: background, borderColor: gray },
  ".cm-button": { color: foreground, backgroundImage: "none", backgroundColor: backgroundSoft, borderColor: gray },
  ".cm-tooltip": { color: foreground, backgroundColor: backgroundHard, borderColor: "#504945" },
  ".cm-tooltip-autocomplete > ul > li[aria-selected]": { color: backgroundHard, backgroundColor: blue },
}, { dark: true });

const syntaxTheme = HighlightStyle.define([
  { tag: tags.comment, color: gray, fontStyle: "italic" },
  { tag: [tags.keyword, tags.operatorKeyword, tags.modifier], color: red },
  { tag: [tags.atom, tags.bool, tags.null], color: purple },
  { tag: [tags.number, tags.integer, tags.float], color: purple },
  { tag: [tags.string, tags.special(tags.string), tags.regexp], color: green },
  { tag: [tags.propertyName, tags.attributeName, tags.labelName], color: aqua },
  { tag: [tags.variableName, tags.definition(tags.variableName)], color: blue },
  { tag: [tags.typeName, tags.className, tags.namespace], color: yellow },
  { tag: [tags.punctuation, tags.separator], color: foreground },
  { tag: [tags.operator, tags.url, tags.link], color: orange },
  { tag: [tags.heading, tags.strong], color: yellow, fontWeight: "bold" },
  { tag: tags.emphasis, color: yellow, fontStyle: "italic" },
  { tag: [tags.meta, tags.annotation], color: orange },
  { tag: tags.invalid, color: foreground, backgroundColor: red, textDecoration: "underline" },
]);

export const gruvbox = [editorTheme, syntaxHighlighting(syntaxTheme)];
