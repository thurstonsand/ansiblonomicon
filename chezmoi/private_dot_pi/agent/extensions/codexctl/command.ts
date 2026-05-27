import type { ExtensionCommandContext } from "@earendil-works/pi-coding-agent";
import type { AutocompleteItem } from "@earendil-works/pi-tui";
import { showCodexPanel } from "./panel.js";
import {
  type CodexSettings,
  loadCodexSettingsState,
  REASONING_SUMMARY_VALUES,
  saveCodexSettings,
  VERBOSITY_VALUES,
} from "./settings.js";

export const CODEX_USAGE =
  "Usage: /codex [fast [on|off]|verbosity low|medium|high|summary auto|concise|detailed|off]";

const COMPLETIONS: AutocompleteItem[] = [
  {
    value: "fast on",
    label: "fast on",
    description: "Enable priority service tier",
  },
  {
    value: "fast off",
    label: "fast off",
    description: "Disable priority service tier",
  },
  {
    value: "verbosity low",
    label: "verbosity low",
    description: "Set Codex text verbosity low",
  },
  {
    value: "verbosity medium",
    label: "verbosity medium",
    description: "Set Codex text verbosity medium",
  },
  {
    value: "verbosity high",
    label: "verbosity high",
    description: "Set Codex text verbosity high",
  },
  {
    value: "summary auto",
    label: "summary auto",
    description: "Use automatic reasoning summaries",
  },
  {
    value: "summary concise",
    label: "summary concise",
    description: "Use concise reasoning summaries",
  },
  {
    value: "summary detailed",
    label: "summary detailed",
    description: "Use detailed reasoning summaries",
  },
  {
    value: "summary off",
    label: "summary off",
    description: "Disable reasoning summaries",
  },
];

export function getCodexArgumentCompletions(argumentPrefix: string): AutocompleteItem[] | null {
  const normalizedPrefix = argumentPrefix.trimStart().toLowerCase();
  const filtered = COMPLETIONS.filter((item) => item.value.startsWith(normalizedPrefix));
  return filtered.length > 0 ? filtered : null;
}

export async function handleCodexCommand(
  args: string,
  ctx: ExtensionCommandContext,
): Promise<void> {
  const parsed = parseCodexCommand(args, ctx.hasUI);
  if (parsed.kind === "error") {
    ctx.ui.notify(parsed.message, "error");
    return;
  }

  if (parsed.kind === "open-panel") {
    await showCodexPanel(ctx);
    return;
  }

  const next = applyCodexCommand(loadCodexSettingsState().settings, parsed);
  saveCodexSettings(next);
  ctx.ui.notify(formatCodexSettings(next), "info");
}

type CodexCommandInvocation =
  | { kind: "open-panel" }
  | { kind: "set-fast"; fast: boolean }
  | { kind: "set-verbosity"; verbosity: CodexSettings["verbosity"] }
  | {
      kind: "set-summary";
      reasoningSummary: CodexSettings["reasoningSummary"];
    };

type CodexCommandParseResult = CodexCommandInvocation | { kind: "error"; message: string };

export function parseCodexCommand(args: string, hasUI: boolean): CodexCommandParseResult {
  const tokens = args.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) {
    return hasUI ? { kind: "open-panel" } : { kind: "error", message: CODEX_USAGE };
  }

  if (tokens[0] === "fast") {
    if (tokens.length === 2 && tokens[1] === "on") return { kind: "set-fast", fast: true };
    if (tokens.length === 2 && tokens[1] === "off") return { kind: "set-fast", fast: false };
    return { kind: "error", message: CODEX_USAGE };
  }

  if (tokens[0] === "verbosity" && tokens.length === 2) {
    if (VERBOSITY_VALUES.includes(tokens[1] as CodexSettings["verbosity"])) {
      return {
        kind: "set-verbosity",
        verbosity: tokens[1] as CodexSettings["verbosity"],
      };
    }
    return { kind: "error", message: CODEX_USAGE };
  }

  if (tokens[0] === "summary" && tokens.length === 2) {
    if (REASONING_SUMMARY_VALUES.includes(tokens[1] as CodexSettings["reasoningSummary"])) {
      return {
        kind: "set-summary",
        reasoningSummary: tokens[1] as CodexSettings["reasoningSummary"],
      };
    }
    return { kind: "error", message: CODEX_USAGE };
  }

  return { kind: "error", message: CODEX_USAGE };
}

function applyCodexCommand(
  settings: CodexSettings,
  invocation: Exclude<CodexCommandInvocation, { kind: "open-panel" }>,
): CodexSettings {
  switch (invocation.kind) {
    case "set-fast":
      return { ...settings, fast: invocation.fast };
    case "set-verbosity":
      return { ...settings, verbosity: invocation.verbosity };
    case "set-summary":
      return { ...settings, reasoningSummary: invocation.reasoningSummary };
  }
}

export function cycleVerbosity(settings: CodexSettings): CodexSettings {
  return {
    ...settings,
    verbosity: cycleValue(settings.verbosity, VERBOSITY_VALUES),
  };
}

export function cycleSummary(settings: CodexSettings): CodexSettings {
  return {
    ...settings,
    reasoningSummary: cycleValue(settings.reasoningSummary, REASONING_SUMMARY_VALUES),
  };
}

export function formatCodexSettings(settings: CodexSettings): string {
  return `Codex: fast ${settings.fast ? "on" : "off"}, verbosity ${settings.verbosity}, summary ${settings.reasoningSummary}`;
}

function cycleValue<T extends string>(value: T, values: readonly T[]): T {
  const index = values.indexOf(value);
  return values[(index + 1) % values.length] ?? values[0] ?? value;
}
