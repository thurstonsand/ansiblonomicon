import { readFileSync } from "node:fs";
import type { ExtensionContext, Theme, ThemeColor } from "@earendil-works/pi-coding-agent";
import type { CompanionTheme } from "../shared/messages.js";

type ThemeBgToken = Parameters<Theme["getBgAnsi"]>[0];

type RawColorValue = string | number;

interface RgbColor {
  r: number;
  g: number;
  b: number;
}

interface RawThemeJson {
  vars?: Record<string, RawColorValue>;
  colors?: Record<string, RawColorValue>;
}

interface ResolvedThemePalette {
  bg?: RgbColor;
  panel?: RgbColor;
  panelAlt?: RgbColor;
  text?: RgbColor;
  muted?: RgbColor;
  dim?: RgbColor;
  border?: RgbColor;
  accent?: RgbColor;
  success?: RgbColor;
  warning?: RgbColor;
  error?: RgbColor;
  bashMode?: RgbColor;
  customMessageLabel?: RgbColor;
  mdHeading?: RgbColor;
  mdLink?: RgbColor;
  mdCode?: RgbColor;
  customMessageBg?: RgbColor;
  userMessageBg?: RgbColor;
}

const DEFAULT_DARK_TEXT: RgbColor = { r: 17, g: 24, b: 39 };
const DEFAULT_LIGHT_TEXT: RgbColor = { r: 255, g: 255, b: 255 };
const DEFAULT_DARK_SURFACE: RgbColor = { r: 0, g: 0, b: 0 };
const DEFAULT_LIGHT_SURFACE: RgbColor = { r: 255, g: 255, b: 255 };

const CUBE_VALUES = [0, 95, 135, 175, 215, 255] as const;
const GRAY_VALUES = Array.from({ length: 24 }, (_, i) => 8 + i * 10);

const STATUS_THEME_COLORS = {
  starting: "muted",
  thinking: "dim",
  responding: "text",
  preparing_tool: "dim",
  reading: "mdCode",
  editing: "warning",
  running: "mdHeading",
  searching: "accent",
  done: "success",
  error: "error",
} as const satisfies Record<string, keyof ResolvedThemePalette>;

const companionThemeCache = new Map<string, CompanionTheme>();

export function buildCompanionThemeForContext(ctx: ExtensionContext): CompanionTheme {
  const cacheKey = ctx.ui.theme.name ?? "<anonymous>";
  const cached = companionThemeCache.get(cacheKey);
  if (cached) return cached;

  const companionTheme = buildCompanionTheme(ctx.ui.theme, readRawTheme(ctx));
  companionThemeCache.set(cacheKey, companionTheme);
  return companionTheme;
}

export function buildCompanionTheme(theme: Theme, rawTheme?: RawThemeJson): CompanionTheme {
  const palette = buildThemePalette(theme, rawTheme);
  const baseSurface = palette.bg ?? palette.userMessageBg ?? palette.customMessageBg;
  const isLightTheme = baseSurface ? !isDark(baseSurface) : theme.name?.includes("light") === true;

  return isLightTheme ? buildPaperGlassTheme(palette) : buildDarkGlassTheme(palette);
}

function buildDarkGlassTheme(palette: ResolvedThemePalette): CompanionTheme {
  const surface =
    palette.bg ?? palette.customMessageBg ?? palette.userMessageBg ?? DEFAULT_DARK_SURFACE;
  const text = ensureReadable(palette.text ?? DEFAULT_LIGHT_TEXT, surface);

  return buildPalette({
    palette,
    surface,
    text,
    surfaceAlpha: 0.92,
    border: palette.border ? hex(palette.border) : rgba(text, 0.38),
    shadow: "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)",
    divider: rgba(text, 0.055),
    attentionPulse: rgba(text, 0.12),
  });
}

function buildPaperGlassTheme(palette: ResolvedThemePalette): CompanionTheme {
  const surface =
    palette.panel ?? palette.customMessageBg ?? palette.userMessageBg ?? DEFAULT_LIGHT_SURFACE;
  const text = ensureReadable(palette.text ?? DEFAULT_DARK_TEXT, surface);

  return buildPalette({
    palette,
    surface,
    text,
    surfaceAlpha: 0.92,
    border: palette.border ? hex(palette.border) : rgba(text, 0.3),
    shadow: "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)",
    divider: rgba(text, 0.055),
    attentionPulse: rgba(text, 0.1),
  });
}

interface BuildPaletteOptions {
  palette: ResolvedThemePalette;
  surface: RgbColor;
  text: RgbColor;
  surfaceAlpha: number;
  border: string;
  shadow: string;
  divider: string;
  attentionPulse: string;
}

function buildPalette(options: BuildPaletteOptions): CompanionTheme {
  const { palette, surface, text, surfaceAlpha, border, shadow, divider, attentionPulse } = options;
  const attentionDot = palette.customMessageLabel ?? palette.accent ?? text;

  return {
    pillBg: rgba(surface, surfaceAlpha),
    border,
    shadow,
    divider,
    text: hex(text),
    muted: rgba(palette.muted ?? text, 0.94),
    subtle: rgba(palette.dim ?? text, 0.82),
    separator: rgba(palette.dim ?? text, 0.6),
    attentionDot: hex(attentionDot),
    attentionGlow: hex(surfaceAwareCharge(attentionDot, surface)),
    attentionPulse,
    dots: Object.fromEntries(
      Object.entries(STATUS_THEME_COLORS).map(([status, token]) => [
        status,
        hex(palette[token] ?? text),
      ]),
    ),
  };
}

function buildThemePalette(theme: Theme, rawTheme: RawThemeJson | undefined): ResolvedThemePalette {
  return {
    bg: readVar(rawTheme, "bg"),
    panel: readVar(rawTheme, "panel"),
    panelAlt: readVar(rawTheme, "panelAlt"),
    text: readRawColor(rawTheme, "text") ?? readVar(rawTheme, "text") ?? readFg(theme, "text"),
    muted: readRawColor(rawTheme, "muted") ?? readVar(rawTheme, "muted") ?? readFg(theme, "muted"),
    dim: readRawColor(rawTheme, "dim") ?? readVar(rawTheme, "dim") ?? readFg(theme, "dim"),
    border:
      readRawColor(rawTheme, "border") ?? readVar(rawTheme, "border") ?? readFg(theme, "border"),
    accent:
      readRawColor(rawTheme, "accent") ?? readVar(rawTheme, "accent") ?? readFg(theme, "accent"),
    success: readRawColor(rawTheme, "success") ?? readFg(theme, "success"),
    warning: readRawColor(rawTheme, "warning") ?? readFg(theme, "warning"),
    error: readRawColor(rawTheme, "error") ?? readFg(theme, "error"),
    bashMode: readRawColor(rawTheme, "bashMode") ?? readFg(theme, "bashMode"),
    customMessageLabel:
      readRawColor(rawTheme, "customMessageLabel") ?? readFg(theme, "customMessageLabel"),
    mdHeading: readRawColor(rawTheme, "mdHeading") ?? readFg(theme, "mdHeading"),
    mdLink: readRawColor(rawTheme, "mdLink") ?? readFg(theme, "mdLink"),
    mdCode: readRawColor(rawTheme, "mdCode") ?? readFg(theme, "mdCode"),
    customMessageBg: readRawColor(rawTheme, "customMessageBg") ?? readBg(theme, "customMessageBg"),
    userMessageBg: readRawColor(rawTheme, "userMessageBg") ?? readBg(theme, "userMessageBg"),
  };
}

function readRawTheme(ctx: ExtensionContext): RawThemeJson | undefined {
  const themeName = ctx.ui.theme.name;
  const themePath =
    ctx.ui.theme.sourcePath ??
    ctx.ui.getAllThemes().find((theme) => theme.name === themeName)?.path;
  if (!themePath) return undefined;

  try {
    const data = JSON.parse(readFileSync(themePath, "utf8")) as unknown;
    if (!data || typeof data !== "object") return undefined;
    return data as RawThemeJson;
  } catch {
    return undefined;
  }
}

function readRawColor(rawTheme: RawThemeJson | undefined, colorName: string): RgbColor | undefined {
  const value = rawTheme?.colors?.[colorName];
  const resolved = resolveRawColor(rawTheme, value);
  if (resolved) return resolved;

  if (isTextColorName(colorName)) return readVar(rawTheme, "text");
  return undefined;
}

function readVar(rawTheme: RawThemeJson | undefined, varName: string): RgbColor | undefined {
  return resolveRawColor(rawTheme, rawTheme?.vars?.[varName]);
}

function resolveRawColor(
  rawTheme: RawThemeJson | undefined,
  value: RawColorValue | undefined,
  visited = new Set<string>(),
): RgbColor | undefined {
  if (value === undefined || value === "") return undefined;
  if (typeof value === "number") return ansi256ToRgb(value);
  if (value.startsWith("#")) return hexToRgb(value);
  if (visited.has(value)) return undefined;

  visited.add(value);
  return resolveRawColor(rawTheme, rawTheme?.vars?.[value], visited);
}

function isTextColorName(colorName: string): boolean {
  return colorName === "text" || colorName.endsWith("Text");
}

function readFg(theme: Theme, token: ThemeColor): RgbColor | undefined {
  try {
    return parseAnsiColor(theme.getFgAnsi(token));
  } catch {
    return undefined;
  }
}

function readBg(theme: Theme, token: ThemeBgToken): RgbColor | undefined {
  try {
    return parseAnsiColor(theme.getBgAnsi(token));
  } catch {
    return undefined;
  }
}

function parseAnsiColor(ansi: string): RgbColor | undefined {
  if (ansi.charCodeAt(0) !== 27 || ansi[1] !== "[" || !ansi.endsWith("m")) return undefined;

  const parts = ansi.slice(2, -1).split(";").map(Number);
  const isColorSequence = parts[0] === 38 || parts[0] === 48;
  if (!isColorSequence) return undefined;

  if (parts[1] === 2 && parts.length >= 5) {
    return {
      r: clamp(parts[2]),
      g: clamp(parts[3]),
      b: clamp(parts[4]),
    };
  }

  if (parts[1] === 5 && parts.length >= 3) return ansi256ToRgb(parts[2]);

  return undefined;
}

function ansi256ToRgb(index: number): RgbColor | undefined {
  if (!Number.isInteger(index) || index < 0 || index > 255) return undefined;

  if (index < 16) {
    return [
      { r: 0, g: 0, b: 0 },
      { r: 128, g: 0, b: 0 },
      { r: 0, g: 128, b: 0 },
      { r: 128, g: 128, b: 0 },
      { r: 0, g: 0, b: 128 },
      { r: 128, g: 0, b: 128 },
      { r: 0, g: 128, b: 128 },
      { r: 192, g: 192, b: 192 },
      { r: 128, g: 128, b: 128 },
      { r: 255, g: 0, b: 0 },
      { r: 0, g: 255, b: 0 },
      { r: 255, g: 255, b: 0 },
      { r: 0, g: 0, b: 255 },
      { r: 255, g: 0, b: 255 },
      { r: 0, g: 255, b: 255 },
      { r: 255, g: 255, b: 255 },
    ][index];
  }

  if (index >= 232) {
    const gray = GRAY_VALUES[index - 232];
    return { r: gray, g: gray, b: gray };
  }

  const colorIndex = index - 16;
  return {
    r: CUBE_VALUES[Math.floor(colorIndex / 36)],
    g: CUBE_VALUES[Math.floor((colorIndex % 36) / 6)],
    b: CUBE_VALUES[colorIndex % 6],
  };
}

function hexToRgb(value: string): RgbColor | undefined {
  const match = /^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(value);
  if (!match) return undefined;
  return {
    r: Number.parseInt(match[1], 16),
    g: Number.parseInt(match[2], 16),
    b: Number.parseInt(match[3], 16),
  };
}

function ensureReadable(preferred: RgbColor, background: RgbColor): RgbColor {
  const preferredContrast = contrastRatio(preferred, background);
  if (preferredContrast >= 4.5) return preferred;

  const darkContrast = contrastRatio(DEFAULT_DARK_TEXT, background);
  const lightContrast = contrastRatio(DEFAULT_LIGHT_TEXT, background);
  return darkContrast > lightContrast ? DEFAULT_DARK_TEXT : DEFAULT_LIGHT_TEXT;
}

function contrastRatio(a: RgbColor, b: RgbColor): number {
  const light = Math.max(luminance(a), luminance(b));
  const dark = Math.min(luminance(a), luminance(b));
  return (light + 0.05) / (dark + 0.05);
}

function luminance({ r, g, b }: RgbColor): number {
  const linear = [r, g, b].map((channel) => {
    const value = channel / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function isDark(color: RgbColor): boolean {
  return luminance(color) < 0.5;
}

function surfaceAwareCharge(color: RgbColor, surface: RgbColor): RgbColor {
  const source = rgbToHsl(color);
  const saturation = Math.min(1, Math.max(0.9, source.s * 1.45));
  const targetContrast = 3.1;
  const surfaceHex = hex(surface);
  let best = hslToRgb({ h: source.h, s: saturation, l: source.l });

  if (isDark(surface)) {
    for (let lightness = Math.max(0.5, source.l); lightness <= 0.78; lightness += 0.015) {
      const candidate = hslToRgb({ h: source.h, s: saturation, l: lightness });
      best = candidate;
      if (contrastRatio(candidate, surface) >= targetContrast) break;
    }
  } else {
    for (let lightness = Math.min(0.52, source.l); lightness >= 0.28; lightness -= 0.015) {
      const candidate = hslToRgb({ h: source.h, s: saturation, l: lightness });
      best = candidate;
      if (contrastRatio(candidate, surface) >= targetContrast) break;
    }
  }

  return hexToRgb(hex(best)) ?? hexToRgb(surfaceHex) ?? best;
}

function rgbToHsl({ r, g, b }: RgbColor): { h: number; s: number; l: number } {
  const red = r / 255;
  const green = g / 255;
  const blue = b / 255;
  const max = Math.max(red, green, blue);
  const min = Math.min(red, green, blue);
  const l = (max + min) / 2;

  if (max === min) return { h: 0, s: 0, l };

  const delta = max - min;
  const s = l > 0.5 ? delta / (2 - max - min) : delta / (max + min);
  const h =
    max === red
      ? ((green - blue) / delta + (green < blue ? 6 : 0)) * 60
      : max === green
        ? ((blue - red) / delta + 2) * 60
        : ((red - green) / delta + 4) * 60;

  return { h, s, l };
}

function hslToRgb({ h, s, l }: { h: number; s: number; l: number }): RgbColor {
  const chroma = (1 - Math.abs(2 * l - 1)) * s;
  const segment = h / 60;
  const x = chroma * (1 - Math.abs((segment % 2) - 1));
  const match = l - chroma / 2;
  const [red, green, blue] =
    segment < 1
      ? [chroma, x, 0]
      : segment < 2
        ? [x, chroma, 0]
        : segment < 3
          ? [0, chroma, x]
          : segment < 4
            ? [0, x, chroma]
            : segment < 5
              ? [x, 0, chroma]
              : [chroma, 0, x];

  return {
    r: (red + match) * 255,
    g: (green + match) * 255,
    b: (blue + match) * 255,
  };
}

function rgba({ r, g, b }: RgbColor, alpha: number): string {
  return `rgba(${r},${g},${b},${alpha})`;
}

function hex({ r, g, b }: RgbColor): string {
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function toHex(value: number): string {
  return clamp(value).toString(16).padStart(2, "0");
}

function clamp(value: number): number {
  return Math.max(0, Math.min(255, Math.round(value)));
}
