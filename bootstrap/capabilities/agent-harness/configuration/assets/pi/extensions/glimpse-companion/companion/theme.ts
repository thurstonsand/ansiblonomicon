import type { Theme, ThemeColor, ThemeToken } from "@earendil-works/pi-coding-agent";
import { colorToRgb } from "@earendil-works/pi-tui";
import type { CompanionTheme } from "../shared/messages.js";

interface RgbColor {
  r: number;
  g: number;
  b: number;
}

const DEFAULT_DARK_TEXT: RgbColor = { r: 17, g: 24, b: 39 };
const DEFAULT_LIGHT_TEXT: RgbColor = { r: 255, g: 255, b: 255 };

const STATUS_THEME_COLORS = {
  starting: "muted",
  thinking: "dim",
  responding: "text",
  preparing_tool: "dim",
  reading: "mdCode",
  editing: "warning",
  running: "mdHeading",
  searching: "accent",
  compacting: "dim",
  done: "success",
  error: "error",
} as const satisfies Record<string, ThemeColor>;

export function buildCompanionTheme(theme: Theme): CompanionTheme {
  const color = (token: ThemeToken): RgbColor => colorToRgb(theme.colors[token]);
  const surface = color("userMessageBg");
  const text = ensureReadable(color("text"), surface);
  const attentionDot = color("customMessageLabel");

  return {
    pillBg: rgba(surface, 0.92),
    border: hex(color("border")),
    shadow: "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)",
    divider: rgba(text, 0.055),
    text: hex(text),
    muted: rgba(color("muted"), 0.94),
    subtle: rgba(color("dim"), 0.82),
    separator: rgba(color("dim"), 0.6),
    attentionDot: hex(attentionDot),
    attentionGlow: hex(surfaceAwareCharge(attentionDot, surface)),
    attentionPulse: rgba(text, theme.appearance === "light" ? 0.1 : 0.12),
    dots: Object.fromEntries(
      Object.entries(STATUS_THEME_COLORS).map(([status, token]) => [status, hex(color(token))]),
    ),
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

  return best;
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
