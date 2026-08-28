import type { Shortcut } from "./types.js";

export const defaultShortcut = (): Shortcut => ({
  action: "new-shell",
  key: "Meta",
  control: false,
  alt: false,
  shift: false,
  meta: false,
});

export const matchesShortcut = (event: KeyboardEvent, shortcut: Shortcut): boolean =>
  event.key.toLowerCase() === shortcut.key.toLowerCase() &&
  event.ctrlKey === shortcut.control &&
  event.altKey === shortcut.alt &&
  event.shiftKey === shortcut.shift &&
  event.metaKey === shortcut.meta;

export const isStandaloneModifier = (shortcut: Shortcut): boolean =>
  ["Control", "Alt", "Shift", "Meta"].includes(shortcut.key) &&
  !shortcut.control &&
  !shortcut.alt &&
  !shortcut.shift &&
  !shortcut.meta;

export const shortcutLabel = (shortcut: Shortcut): string =>
  [
    ...(shortcut.control ? ["Ctrl"] : []),
    ...(shortcut.alt ? ["Alt"] : []),
    ...(shortcut.shift ? ["Shift"] : []),
    ...(shortcut.meta ? ["Meta"] : []),
    shortcut.key,
  ].join(" + ");

export const captureShortcut = (event: KeyboardEvent): Shortcut => ({
  action: "new-shell",
  key: event.key,
  control: event.ctrlKey && event.key !== "Control",
  alt: event.altKey && event.key !== "Alt",
  shift: event.shiftKey && event.key !== "Shift",
  meta: event.metaKey && event.key !== "Meta",
});
