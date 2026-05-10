import { basename } from "node:path";
import type { Theme, ThemeColor } from "@earendil-works/pi-coding-agent";

import { colorForPercent, renderGauge } from "./gauge.js";
import {
  ALL_FG_TOKENS,
  currentGitBranch,
  detectDefaultThemeName,
  loadThemeForPreview,
  parsePreviewArgs,
  readConfiguredThemeName,
} from "./preview-helpers.js";

type FooterColorPlan = {
  label: string;
  model: ThemeColor;
  path: ThemeColor;
  git: ThemeColor;
  separator: ThemeColor;
  separatorGlyph?: string;
  modelText?: string;
  branchText?: string;
};

const TEXT_LIGHTNING = "⚡︎";
const NF_FOLDER_OPEN = "\u{F115}";
const NF_BRANCH = "\u{F126}";

const args = parsePreviewArgs(process.argv.slice(2));
const previewCwd = process.env.INIT_CWD || process.cwd();
const percent = args.percent ?? 64;
const themeName = args.theme ?? readConfiguredThemeName() ?? detectDefaultThemeName();
const { theme, path: themePath } = loadThemeForPreview(themeName, previewCwd);
const branch = currentGitBranch(previewCwd);
const cwdName = basename(previewCwd);
const separatorTokens = args.all ? ALL_FG_TOKENS : defaultSeparatorTokens();

console.log(`theme: ${theme.name ?? themeName} (${themePath})`);
console.log("scene: locked footer colors, separator color lab");
console.log(`sample: context=${percent}% model=moon+fast`);
console.log("");

console.log(theme.fg("dim", "locked color decisions"));
for (const plan of buildLockedDecisionPlans()) {
  printFooterPlan(plan);
}

console.log("");
console.log(theme.fg("dim", "mainline branch hazard"));
for (const plan of buildBranchHazardPlans()) {
  printFooterPlan(plan);
}

console.log("");
console.log(theme.fg("dim", "separator token trials"));
for (const token of separatorTokens) {
  printFooterPlan({
    ...lockedOpenAiPlan(`sep:${token}`),
    separator: token,
  });
}

console.log("");
console.log(theme.fg("dim", "separator shape × color shortlist"));
for (const plan of buildSeparatorMatrix()) {
  printFooterPlan(plan);
}

console.log("");
console.log(
  "Run with: npm --prefix chezmoi/private_dot_pi/agent/extensions run preview:gauge:colors -- --percent 64 --theme gruvbox-light-hard [--all]",
);

function defaultSeparatorTokens(): ThemeColor[] {
  return [
    "border",
    "borderMuted",
    "dim",
    "muted",
    "syntaxPunctuation",
    "syntaxOperator",
    "syntaxComment",
    "mdHr",
    "accent",
    "text",
  ];
}

function buildLockedDecisionPlans(): FooterColorPlan[] {
  return [
    lockedOpenAiPlan("openai text"),
    {
      ...lockedOpenAiPlan("claude syntaxNumber"),
      model: "syntaxNumber",
      modelText: `✴ claude 4.5² [● ${TEXT_LIGHTNING}]`,
    },
    {
      ...lockedOpenAiPlan("gemini thinkingLow"),
      model: "thinkingLow",
      modelText: `✦ gemini 3 pro² [● ${TEXT_LIGHTNING}]`,
    },
  ];
}

function buildBranchHazardPlans(): FooterColorPlan[] {
  return [
    {
      ...lockedOpenAiPlan("feature muted"),
      branchText: "feature/footer-tuning",
      git: "muted",
    },
    {
      ...lockedOpenAiPlan("main warning"),
      branchText: "main",
      git: "warning",
    },
    {
      ...lockedOpenAiPlan("master warning"),
      branchText: "master",
      git: "warning",
    },
  ];
}

function buildSeparatorMatrix(): FooterColorPlan[] {
  const glyphs = ["❯", "›", "┆", "┊", "│", "╱", "·"];
  const colors: ThemeColor[] = ["borderMuted", "dim", "muted", "syntaxPunctuation"];
  return glyphs.flatMap((separatorGlyph) =>
    colors.map((separator) => ({
      ...lockedOpenAiPlan(`${separatorGlyph} ${separator}`),
      separator,
      separatorGlyph,
    })),
  );
}

function lockedOpenAiPlan(label: string): FooterColorPlan {
  return {
    label,
    model: "text",
    path: "bashMode",
    git: branchColor(branch),
    separator: "borderMuted",
  };
}

function branchColor(value: string | null): ThemeColor {
  return value === "main" || value === "master" ? "warning" : "muted";
}

function printFooterPlan(plan: FooterColorPlan): void {
  console.log(theme.fg("dim", `${plan.label.padEnd(24)} `) + renderFooterPlan(theme, plan));
}

function renderFooterPlan(activeTheme: Theme, plan: FooterColorPlan): string {
  const model = activeTheme.fg(plan.model, plan.modelText ?? `❁ gpt 5.1² [● ${TEXT_LIGHTNING}]`);
  const path = activeTheme.fg(plan.path, `${NF_FOLDER_OPEN} ${cwdName}`);
  const displayedBranch = plan.branchText ?? branch;
  const git = displayedBranch ? activeTheme.fg(plan.git, `${NF_BRANCH} ${displayedBranch}`) : "";
  const sep = activeTheme.fg(plan.separator, plan.separatorGlyph ?? "/");
  const gauge = activeTheme.fg(colorForPercent(percent), renderGauge(percent));
  return [model, sep, path, displayedBranch ? sep : null, git || null, sep, gauge]
    .filter(Boolean)
    .join(" ");
}
