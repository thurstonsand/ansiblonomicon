import type { SegmentContext, SegmentLoaderAPI, StatusLineSegment } from "pi-powerline-footer";
import type { ThemeColor } from "@mariozechner/pi-coding-agent";

const DEFAULT_WARN_AT = 50;
const DEFAULT_ERROR_AT = 80;
const GAUGE_WIDTH = 12;
const RESET_FG = "\x1b[39m";
const RESET_BG = "\x1b[49m";
const FG_TRUECOLOR_PREFIX = "\x1b[38;2;";
const FG_256_PREFIX = "\x1b[38;5;";
const BG_TRUECOLOR_PREFIX = "\x1b[48;2;";
const BG_256_PREFIX = "\x1b[48;5;";
const ALLOWED_OPTION_KEYS = new Set(["maxTokens", "warnAt", "errorAt"]);

interface RGB {
  r: number;
  g: number;
  b: number;
}

const ANSI_256_BASE_COLORS: readonly RGB[] = [
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
];

const ANSI_256_CUBE_VALUES = [0, 95, 135, 175, 215, 255];

interface ContextGaugeOptions {
  maxTokens?: number;
  warnAt?: number;
  errorAt?: number;
}

interface ResolvedContextGaugeOptions {
  maxTokens?: number;
  warnAt: number;
  errorAt: number;
}

export default function ({ registerSegment }: SegmentLoaderAPI): void {
  const segment: StatusLineSegment<ContextGaugeOptions> = {
    id: "context_pct",
    render(ctx: SegmentContext, options) {
      if (ctx.contextWindow <= 0) {
        return { content: "", visible: false };
      }

      const resolvedOptions = resolveOptions(options);
      const contextTokens = Math.round((ctx.contextPercent / 100) * ctx.contextWindow);
      const effectiveMax = resolvedOptions.maxTokens === undefined
        ? ctx.contextWindow
        : Math.min(ctx.contextWindow, resolvedOptions.maxTokens);
      const isOverSoftMax = resolvedOptions.maxTokens !== undefined
        && effectiveMax < ctx.contextWindow
        && contextTokens > effectiveMax;
      const displayedPercent = isOverSoftMax
        ? (contextTokens / ctx.contextWindow) * 100
        : (contextTokens / effectiveMax) * 100;
      const colorName = getColorName(displayedPercent, resolvedOptions, isOverSoftMax);
      const gauge = renderGauge(ctx, displayedPercent, colorName);
      const content = isOverSoftMax ? `${ctx.theme.fg("error", "🔥")}${gauge}` : gauge;

      return {
        content,
        visible: true,
      };
    },
  };

  registerSegment(segment);
}

function resolveOptions(options: ContextGaugeOptions | undefined): ResolvedContextGaugeOptions {
  if (options === undefined) {
    return {
      warnAt: DEFAULT_WARN_AT,
      errorAt: DEFAULT_ERROR_AT,
    };
  }

  if (typeof options !== "object" || options === null || Array.isArray(options)) {
    throw new Error("context_pct options must be an object");
  }

  for (const key of Object.keys(options)) {
    if (!ALLOWED_OPTION_KEYS.has(key)) {
      throw new Error(`context_pct received unknown option: ${key}`);
    }
  }

  const { maxTokens, warnAt, errorAt } = options;

  if (maxTokens !== undefined && (typeof maxTokens !== "number" || !Number.isFinite(maxTokens) || maxTokens <= 0)) {
    throw new Error("context_pct option maxTokens must be a finite number greater than zero");
  }

  if (warnAt !== undefined && (typeof warnAt !== "number" || !Number.isFinite(warnAt))) {
    throw new Error("context_pct option warnAt must be a finite number");
  }

  if (errorAt !== undefined && (typeof errorAt !== "number" || !Number.isFinite(errorAt))) {
    throw new Error("context_pct option errorAt must be a finite number");
  }

  return {
    maxTokens,
    warnAt: warnAt ?? DEFAULT_WARN_AT,
    errorAt: errorAt ?? DEFAULT_ERROR_AT,
  };
}

function getColorName(displayedPercent: number, options: ResolvedContextGaugeOptions, isOverSoftMax: boolean): ThemeColor {
  if (isOverSoftMax) {
    return "error";
  }

  if (displayedPercent >= options.errorAt) {
    return "error";
  }

  if (displayedPercent >= options.warnAt) {
    return "warning";
  }

  return "success";
}

function renderGauge(ctx: SegmentContext, displayedPercent: number, colorName: ThemeColor): string {
  const clampedPercent = Math.max(0, Math.min(displayedPercent, 100));
  const filledCells = Math.round((clampedPercent / 100) * GAUGE_WIDTH);
  const percentText = `${Math.round(displayedPercent)}%`;
  const startIndex = Math.floor((GAUGE_WIDTH - percentText.length) / 2);
  const endIndex = startIndex + percentText.length;
  const { backgroundAnsi, contrastFg } = resolveFillAnsi(ctx.theme.getFgAnsi(colorName));

  const cells: string[] = [];
  for (let index = 0; index < GAUGE_WIDTH; index += 1) {
    const isFilled = index < filledCells;
    const isTextCell = index >= startIndex && index < endIndex;

    if (!isTextCell) {
      cells.push(isFilled ? `${backgroundAnsi} ${RESET_BG}` : " ");
      continue;
    }

    const char = percentText[index - startIndex];
    if (isFilled) {
      cells.push(`${backgroundAnsi}${contrastFg}${char}${RESET_FG}${RESET_BG}`);
      continue;
    }

    cells.push(ctx.theme.fg("text", char));
  }

  return `${ctx.theme.fg(colorName, "[")}${cells.join("")}${ctx.theme.fg(colorName, "]")}`;
}

interface FillAnsi {
  backgroundAnsi: string;
  contrastFg: string;
}

function resolveFillAnsi(fgAnsi: string): FillAnsi {
  const rgb = parseFgAnsi(fgAnsi);
  const luminance = (0.299 * rgb.r) + (0.587 * rgb.g) + (0.114 * rgb.b);
  const contrastFg = luminance >= 160 ? "\x1b[30m" : "\x1b[97m";

  if (fgAnsi.startsWith(FG_TRUECOLOR_PREFIX)) {
    return { backgroundAnsi: fgAnsi.replace(FG_TRUECOLOR_PREFIX, BG_TRUECOLOR_PREFIX), contrastFg };
  }

  return { backgroundAnsi: fgAnsi.replace(FG_256_PREFIX, BG_256_PREFIX), contrastFg };
}

function parseFgAnsi(fgAnsi: string): RGB {
  if (fgAnsi.startsWith(FG_TRUECOLOR_PREFIX) && fgAnsi.endsWith("m")) {
    const [r, g, b] = fgAnsi.slice(FG_TRUECOLOR_PREFIX.length, -1).split(";").map((value) => Number.parseInt(value, 10));
    return { r, g, b };
  }

  if (fgAnsi.startsWith(FG_256_PREFIX) && fgAnsi.endsWith("m")) {
    const colorIndex = Number.parseInt(fgAnsi.slice(FG_256_PREFIX.length, -1), 10);
    return color256ToRgb(colorIndex);
  }

  throw new Error(`Unsupported foreground ANSI sequence: ${JSON.stringify(fgAnsi)}`);
}

function color256ToRgb(colorIndex: number): RGB {
  if (colorIndex < 16) {
    return ANSI_256_BASE_COLORS[colorIndex];
  }

  if (colorIndex >= 232) {
    const level = 8 + ((colorIndex - 232) * 10);
    return { r: level, g: level, b: level };
  }

  const normalized = colorIndex - 16;
  const rIndex = Math.floor(normalized / 36);
  const gIndex = Math.floor((normalized % 36) / 6);
  const bIndex = normalized % 6;

  return {
    r: ANSI_256_CUBE_VALUES[rIndex],
    g: ANSI_256_CUBE_VALUES[gIndex],
    b: ANSI_256_CUBE_VALUES[bIndex],
  };
}
