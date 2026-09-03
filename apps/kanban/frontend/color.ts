const DARK_INK = "#1d2021";
const LIGHT_INK = "#fbf1c7";
const HEX_COLOR = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

const linearChannel = (channel: number): number => {
  const value = channel / 255;
  return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
};

function relativeLuminance(background: string): number | null {
  if (!HEX_COLOR.test(background)) return null;
  const compact = background.slice(1);
  const expanded = compact.length === 3
    ? [...compact].map((value) => value.repeat(2)).join("") : compact;
  const channels = [0, 2, 4].map((offset) => linearChannel(
    Number.parseInt(expanded.slice(offset, offset + 2), 16)));
  return 0.2126 * channels[0]! + 0.7152 * channels[1]! + 0.0722 * channels[2]!;
}

const contrastRatio = (left: number, right: number): number =>
  (Math.max(left, right) + 0.05) / (Math.min(left, right) + 0.05);

export function contrastInk(background: string): string {
  const luminance = relativeLuminance(background);
  if (luminance === null) return LIGHT_INK;
  return contrastRatio(luminance, relativeLuminance(DARK_INK)!) >=
    contrastRatio(luminance, relativeLuminance(LIGHT_INK)!) ? DARK_INK : LIGHT_INK;
}

export function coloredSurfaceStyle(backgroundProperty: string, inkProperty: string,
  background: string): string {
  return `${backgroundProperty}:${background};${inkProperty}:${contrastInk(background)}`;
}
