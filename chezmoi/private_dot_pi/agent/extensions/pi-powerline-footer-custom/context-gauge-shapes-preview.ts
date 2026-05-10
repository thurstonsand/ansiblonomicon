import { basename } from "node:path";
import type { Theme, ThemeColor } from "@earendil-works/pi-coding-agent";

import { colorForPercent, renderGauge } from "./gauge.js";
import {
  currentGitBranch,
  detectDefaultThemeName,
  loadThemeForPreview,
  parsePreviewArgs,
  readConfiguredThemeName,
} from "./preview-helpers.js";

type Verbosity = "low" | "medium" | "high";

type Variant = {
  label: string;
  separator: string;
  separatorColor?: ThemeColor;
};

type SeparatorCandidate = {
  label: string;
  separator: string;
  note?: string;
};

const TEXT_LIGHTNING = "⚡︎";
const NF_FOLDER_OPEN = "\u{F115}";
const NF_BRANCH = "\u{F126}";
const POWERLINE = "\u{E0B0}";
const POWERLINE_THIN = "\u{E0B1}";

const args = parsePreviewArgs(process.argv.slice(2));
const previewCwd = process.env.INIT_CWD || process.cwd();
const themeName = args.theme ?? readConfiguredThemeName() ?? detectDefaultThemeName();
const { theme, path: themePath } = loadThemeForPreview(themeName, previewCwd);
const cwdName = basename(previewCwd);
const branch = currentGitBranch(previewCwd);
const percent = args.percent ?? 64;
const verbosity = parseVerbosity(args.verbosity) ?? "high";

console.log(`theme: ${theme.name ?? themeName} (${themePath})`);
console.log("scene: locked footer decisions, separator lab");
console.log(`sample: context=${percent}% verbosity=${verbosity} fast=on`);
console.log("");

console.log(theme.fg("dim", "locked footer state"));
printVariant("current", { label: "current", separator: "/" });

console.log("");
console.log(theme.fg("dim", "built-in pi-powerline styles"));
for (const candidate of buildPowerlineStyleCandidates()) {
  printSeparatorCandidate(candidate);
}

console.log("");
console.log(theme.fg("dim", "separator shape trials"));
for (const candidate of buildSeparatorCandidates()) {
  printSeparatorCandidate(candidate);
}

console.log("");
console.log(theme.fg("dim", "separator color smoke test"));
for (const variant of buildSeparatorColorSmokeTest()) {
  printVariant(variant.label, variant);
}

console.log("");
console.log(theme.fg("dim", "focused separator smoke test"));
for (const variant of buildFocusedSeparatorSmokeTest()) {
  printVariant(variant.label, variant);
  console.log("");
}
console.log(theme.fg("dim", "separator glyph intent"));
for (const candidate of [...buildPowerlineStyleCandidates(), ...buildSeparatorCandidates()]) {
  console.log(
    theme.fg("dim", `${candidate.label.padEnd(18)} ${describeGlyph(candidate.separator)}`),
  );
}

console.log("");
console.log(
  "Run with: npm --prefix chezmoi/private_dot_pi/agent/extensions run preview:gauge:shapes -- --percent 64 --verbosity high --theme gruvbox-light-hard",
);

function buildPowerlineStyleCandidates(): SeparatorCandidate[] {
  return [
    { label: "powerline", separator: POWERLINE, note: "built-in style: powerline" },
    { label: "powerline-thin", separator: POWERLINE_THIN, note: "current configured style" },
    { label: "slash", separator: "/", note: "built-in style: slash" },
    { label: "pipe", separator: "|", note: "built-in style: pipe" },
    { label: "dot", separator: "·", note: "built-in style: dot" },
    { label: "chevron", separator: "›", note: "built-in style: chevron" },
    { label: "star", separator: "✦", note: "built-in style: star" },
  ];
}

function buildSeparatorCandidates(): SeparatorCandidate[] {
  return [
    { label: "heavy chevron", separator: "❯", note: "current preview language" },
    { label: "thin chevron", separator: "›", note: "quiet directional" },
    { label: "small triangle", separator: "▹", note: "directional, less powerline" },
    { label: "triangle", separator: "▸", note: "stronger pointer" },
    { label: "vertical", separator: "│", note: "strict rail" },
    { label: "broken rail", separator: "┆", note: "NieR-ish scanline" },
    { label: "micro rail", separator: "┊", note: "lighter scanline" },
    { label: "slashed rail", separator: "╱", note: "mechanical cut" },
    { label: "dot", separator: "·", note: "soft delimiter" },
    { label: "double dot", separator: "ꞏ", note: "narrow dot" },
    { label: "therefore", separator: "∴", note: "operator-like" },
    { label: "wave", separator: "⌁", note: "signal/noise" },
  ];
}

function buildSeparatorColorSmokeTest(): Variant[] {
  return [
    { label: "border", separator: "❯", separatorColor: "border" },
    { label: "borderMuted", separator: "❯", separatorColor: "borderMuted" },
    { label: "dim", separator: "❯", separatorColor: "dim" },
    { label: "muted", separator: "❯", separatorColor: "muted" },
    { label: "accent", separator: "❯", separatorColor: "accent" },
  ];
}

function buildFocusedSeparatorSmokeTest(): Variant[] {
  const colors: ThemeColor[] = [
    "border",
    "borderMuted",
    "dim",
    "muted",
    "syntaxPunctuation",
    "syntaxOperator",
    "accent",
  ];
  return ["╱", "▸"].flatMap((separator) =>
    colors.map((separatorColor) => ({
      label: `${separator} ${separatorColor}`,
      separator,
      separatorColor,
    })),
  );
}

function printSeparatorCandidate(candidate: SeparatorCandidate): void {
  printVariant(candidate.label, { label: candidate.label, separator: candidate.separator });
  if (candidate.note) console.log(theme.fg("dim", `${"".padEnd(18)} ${candidate.note}`));
}

function printVariant(label: string, variant: Variant): void {
  console.log(theme.fg("dim", `${label.padEnd(18)} `) + renderStatusRow(theme, variant));
}

function renderStatusRow(activeTheme: Theme, variant: Variant): string {
  const model = activeTheme.fg(
    providerModelColor(),
    `❁ gpt 5.1² [${moonSignalIcon(verbosity)} ${TEXT_LIGHTNING}]`,
  );
  const path = activeTheme.fg("bashMode", `${NF_FOLDER_OPEN} ${cwdName}`);
  const git = branch ? activeTheme.fg(branchColor(branch), `${NF_BRANCH} ${branch}`) : "";
  const context = activeTheme.fg(colorForPercent(percent), renderGauge(percent));
  const sep = activeTheme.fg(variant.separatorColor ?? "border", variant.separator);
  return [model, sep, path, branch ? sep : null, git || null, sep, context]
    .filter(Boolean)
    .join(" ");
}

function providerModelColor(): ThemeColor {
  return "text";
}

function branchColor(value: string): ThemeColor {
  return value === "main" || value === "master" ? "warning" : "muted";
}

function moonSignalIcon(level: Verbosity): string {
  switch (level) {
    case "high":
      return "●";
    case "medium":
      return "◐";
    default:
      return "◔";
  }
}

function describeGlyph(glyph: string): string {
  return `${glyph}  ${codePoints(glyph).join(" ")}`;
}

function codePoints(value: string): string[] {
  return Array.from(value, (char) => {
    const codePoint = char.codePointAt(0) ?? 0;
    return `U+${codePoint.toString(16).toUpperCase().padStart(4, "0")}`;
  });
}

function parseVerbosity(value: string | undefined): Verbosity | undefined {
  if (value === "low" || value === "medium" || value === "high") return value;
  return undefined;
}
