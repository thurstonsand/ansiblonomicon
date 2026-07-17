import { execSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { isAbsolute, join, resolve } from "node:path";

import { getPackageDir, Theme, type ThemeColor } from "@earendil-works/pi-coding-agent";

type ThemeBg =
  | "selectedBg"
  | "userMessageBg"
  | "customMessageBg"
  | "toolPendingBg"
  | "toolSuccessBg"
  | "toolErrorBg";

type ThemeJson = {
  name?: string;
  vars?: Record<string, string | number>;
  colors: Record<string, string | number>;
};

const FG_TOKEN_NAMES = [
  "accent",
  "border",
  "borderAccent",
  "borderMuted",
  "success",
  "error",
  "warning",
  "muted",
  "dim",
  "text",
  "thinkingText",
  "userMessageText",
  "customMessageText",
  "customMessageLabel",
  "toolTitle",
  "toolOutput",
  "mdHeading",
  "mdLink",
  "mdLinkUrl",
  "mdCode",
  "mdCodeBlock",
  "mdCodeBlockBorder",
  "mdQuote",
  "mdQuoteBorder",
  "mdHr",
  "mdListBullet",
  "toolDiffAdded",
  "toolDiffRemoved",
  "toolDiffContext",
  "syntaxComment",
  "syntaxKeyword",
  "syntaxFunction",
  "syntaxVariable",
  "syntaxString",
  "syntaxNumber",
  "syntaxType",
  "syntaxOperator",
  "syntaxPunctuation",
  "thinkingOff",
  "thinkingMinimal",
  "thinkingLow",
  "thinkingMedium",
  "thinkingHigh",
  "thinkingXhigh",
  "bashMode",
] as const satisfies readonly ThemeColor[];

const BG_TOKEN_NAMES = [
  "selectedBg",
  "userMessageBg",
  "customMessageBg",
  "toolPendingBg",
  "toolSuccessBg",
  "toolErrorBg",
] as const satisfies readonly ThemeBg[];

const FG_TOKENS = new Set<string>(FG_TOKEN_NAMES);
const BG_TOKENS = new Set<string>(BG_TOKEN_NAMES);

export const ALL_FG_TOKENS = FG_TOKEN_NAMES;

export function loadThemeForPreview(
  themeName: string,
  cwd: string,
): { theme: Theme; path: string } {
  const themePath = resolveThemePath(themeName, cwd);
  return { theme: loadTheme(themePath), path: themePath };
}

export function readConfiguredThemeName(): string | undefined {
  const settingsPath = join(homedir(), ".pi", "agent", "settings.json");
  if (!existsSync(settingsPath)) return undefined;
  try {
    const settings = JSON.parse(readFileSync(settingsPath, "utf8")) as { theme?: unknown };
    return typeof settings.theme === "string" ? settings.theme : undefined;
  } catch {
    return undefined;
  }
}

export function detectDefaultThemeName(): string {
  try {
    return readFileSync(join(homedir(), ".terminal-bg"), "utf8").trim() === "light"
      ? "gruvbox-light-hard"
      : "gruvbox-dark-hard";
  } catch {
    return "gruvbox-dark-hard";
  }
}

export function currentGitBranch(cwd: string): string | null {
  try {
    return (
      execSync("git branch --show-current", {
        cwd,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
      }).trim() || null
    );
  } catch {
    return null;
  }
}

function resolveThemePath(themeNameOrPath: string, cwd: string): string {
  const direct = isAbsolute(themeNameOrPath) ? themeNameOrPath : resolve(cwd, themeNameOrPath);
  if (existsSync(direct)) return direct;

  const repoRoot = resolve(__dirname, "../../../../..");
  const piPackageDir = getPackageDir();
  const candidates = [
    join(homedir(), ".pi", "agent", "themes", `${themeNameOrPath}.json`),
    join(cwd, ".pi", "themes", `${themeNameOrPath}.json`),
    join(repoRoot, ".pi", "themes", `${themeNameOrPath}.json`),
    join(
      homedir(),
      ".pi",
      "agent",
      "git",
      "github.com",
      "hasit",
      "pi-community-themes",
      "themes",
      `${themeNameOrPath}.json`,
    ),
    join(repoRoot, "chezmoi", "private_dot_pi", "agent", "themes", `${themeNameOrPath}.json`),
    join(piPackageDir, "theme", `${themeNameOrPath}.json`),
    join(piPackageDir, "dist", "modes", "interactive", "theme", `${themeNameOrPath}.json`),
    join(piPackageDir, "src", "modes", "interactive", "theme", `${themeNameOrPath}.json`),
  ];

  const found = candidates.find((path) => existsSync(path));
  if (!found) throw new Error(`Theme not found: ${themeNameOrPath}`);
  return found;
}

function loadTheme(themePath: string): Theme {
  const raw = JSON.parse(readFileSync(themePath, "utf8")) as ThemeJson;
  const resolved = resolveThemeColors(raw);
  const fgColors: Record<string, string | number> = {};
  const bgColors: Record<string, string | number> = {};

  for (const [key, value] of Object.entries(resolved)) {
    if (BG_TOKENS.has(key)) bgColors[key] = value;
    else if (FG_TOKENS.has(key)) fgColors[key] = value;
  }

  return new Theme(
    fgColors as Record<ThemeColor, string | number>,
    bgColors as Record<ThemeBg, string | number>,
    "truecolor",
    {
      name: raw.name,
      sourcePath: themePath,
    },
  );
}

function resolveThemeColors(themeJson: ThemeJson): Record<string, string | number> {
  const vars = themeJson.vars ?? {};
  const colors = themeJson.colors ?? {};

  function resolveValue(value: string | number, seen = new Set<string>()): string | number {
    if (typeof value === "number" || value === "" || value.startsWith("#")) return value;
    if (seen.has(value)) throw new Error(`Circular theme variable reference: ${value}`);
    const next = vars[value] ?? colors[value];
    if (next === undefined) throw new Error(`Theme variable not found: ${value}`);
    seen.add(value);
    return resolveValue(next, seen);
  }

  return Object.fromEntries(
    Object.entries(colors).map(([key, value]) => [key, resolveValue(value)]),
  );
}

type ParsedArgs = {
  theme?: string;
  percent?: number;
  verbosity?: string;
  all?: boolean;
};

export function parsePreviewArgs(argv: string[]): ParsedArgs {
  const parsed: ParsedArgs = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--all") parsed.all = true;
    else if (arg === "--theme") parsed.theme = argv[++index];
    else if (arg.startsWith("--theme=")) parsed.theme = arg.slice("--theme=".length);
    else if (arg === "--percent") parsed.percent = Number.parseFloat(argv[++index]);
    else if (arg.startsWith("--percent="))
      parsed.percent = Number.parseFloat(arg.slice("--percent=".length));
    else if (arg === "--verbosity") parsed.verbosity = argv[++index];
    else if (arg.startsWith("--verbosity=")) parsed.verbosity = arg.slice("--verbosity=".length);
  }
  return parsed;
}
