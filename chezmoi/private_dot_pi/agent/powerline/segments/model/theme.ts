import type { Theme, ThemeColor } from "@mariozechner/pi-coding-agent";

const THINKING_TEXT_UNICODE: Record<string, string> = {
  minimal: "[min]",
  low: "[low]",
  medium: "[med]",
  high: "[high]",
  xhigh: "[xhi]",
};

const THINKING_TEXT_NERD: Record<string, string> = {
  minimal: "\u{F0E7} min",
  low: "\u{F10C} low",
  medium: "\u{F192} med",
  high: "\u{F111} high",
  xhigh: "\u{F06D} xhi",
};

const PROVIDER_MODEL_ICONS: Record<string, string> = {
  openai: "❁",
  anthropic: "✴️",
  google: "✨",
};
const NERD_MODEL_ICON = "\uEC19";
const ASCII_MODEL_ICON = "◈";
const NERD_FAST_ICON = "\u{F0068}";
const ASCII_FAST_ICON = "⚡";

export function withIcon(icon: string, text: string): string {
  return icon ? `${icon} ${text}` : text;
}

export function hasNerdFonts(): boolean {
  if (process.env.POWERLINE_NERD_FONTS === "1") return true;
  if (process.env.POWERLINE_NERD_FONTS === "0") return false;
  if (process.env.GHOSTTY_RESOURCES_DIR) return true;

  const term = (process.env.TERM_PROGRAM || "").toLowerCase();
  const nerdTerms = ["iterm", "wezterm", "kitty", "ghostty", "alacritty"];
  return nerdTerms.some((value) => term.includes(value));
}

export function getModelIcon(provider?: string): string {
  const normalizedProvider = provider?.trim().toLowerCase();
  if (normalizedProvider && PROVIDER_MODEL_ICONS[normalizedProvider]) {
    return PROVIDER_MODEL_ICONS[normalizedProvider];
  }

  return hasNerdFonts() ? NERD_MODEL_ICON : ASCII_MODEL_ICON;
}

export function getThinkingText(level: string): string | undefined {
  return hasNerdFonts() ? THINKING_TEXT_NERD[level] : THINKING_TEXT_UNICODE[level];
}

export function getFastIcon(): string {
  return hasNerdFonts() ? NERD_FAST_ICON : ASCII_FAST_ICON;
}

function isHexColor(color: string): color is `#${string}` {
  return /^#[0-9a-fA-F]{6}$/.test(color);
}

function hexToAnsi(hex: `#${string}`): string {
  const normalized = hex.replace("#", "");
  const r = parseInt(normalized.slice(0, 2), 16);
  const g = parseInt(normalized.slice(2, 4), 16);
  const b = parseInt(normalized.slice(4, 6), 16);
  return `\x1b[38;2;${r};${g};${b}m`;
}

export function applyColor(theme: Theme | undefined, color: string, text: string): string {
  if (!theme?.fg) {
    return text;
  }

  if (isHexColor(color)) {
    return `${hexToAnsi(color)}${text}\x1b[0m`;
  }

  try {
    return theme.fg(color as ThemeColor, text);
  } catch {
    return theme.fg("text", text);
  }
}
