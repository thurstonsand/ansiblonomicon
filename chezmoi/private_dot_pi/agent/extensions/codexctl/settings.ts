import { existsSync, type FSWatcher, readFileSync, watch, writeFileSync } from "node:fs";
import path from "node:path";
import { getAgentDir } from "@earendil-works/pi-coding-agent";

export const VERBOSITY_VALUES = ["low", "medium", "high"] as const;
export const REASONING_SUMMARY_VALUES = ["auto", "concise", "detailed", "off"] as const;

export type CodexVerbosity = (typeof VERBOSITY_VALUES)[number];
export type CodexReasoningSummary = (typeof REASONING_SUMMARY_VALUES)[number];

export interface CodexSettings {
  fast: boolean;
  verbosity: CodexVerbosity;
  reasoningSummary: CodexReasoningSummary;
}

export interface CodexSettingsState {
  settings: CodexSettings;
  issues: string[];
}

export const DEFAULT_CODEX_SETTINGS: CodexSettings = {
  fast: false,
  verbosity: "low",
  reasoningSummary: "auto",
};

let cachedState: CodexSettingsState | undefined;
let settingsWatcher: FSWatcher | undefined;

export function getSettingsPath(): string {
  return path.join(getAgentDir(), "settings.json");
}

export function loadCodexSettings(): CodexSettings {
  return loadCodexSettingsState().settings;
}

export function loadCodexSettingsState(): CodexSettingsState {
  cachedState ??= readCodexSettingsState();
  return cachedState;
}

export function startCodexSettingsWatcher(): void {
  cachedState = readCodexSettingsState();

  if (settingsWatcher) return;

  try {
    settingsWatcher = watch(getSettingsPath(), { persistent: false }, () => {
      try {
        cachedState = readCodexSettingsState();
      } catch (error) {
        cachedState = {
          settings: DEFAULT_CODEX_SETTINGS,
          issues: [`Unable to read settings.codex: ${formatError(error)}`],
        };
      }
    });
    settingsWatcher.on("error", () => {
      settingsWatcher?.close();
      settingsWatcher = undefined;
    });
  } catch {
    settingsWatcher = undefined;
  }
}

export function saveCodexSettings(settings: CodexSettings): void {
  const settingsPath = getSettingsPath();
  const root = readSettingsRoot();
  const codex = normalizeCodexSettings(settings).settings;
  const nextRoot = { ...root, codex };
  writeFileSync(settingsPath, `${JSON.stringify(nextRoot, null, 2)}\n`, "utf8");
  cachedState = { settings: codex, issues: [] };
}

export function normalizeCodexSettings(value: unknown): CodexSettingsState {
  const issues: string[] = [];
  const raw = isObject(value) ? value : {};
  if (value !== undefined && !isObject(value)) {
    issues.push("settings.codex must be an object; using defaults");
  }

  return {
    settings: {
      fast: normalizeBoolean(raw.fast, "fast", DEFAULT_CODEX_SETTINGS.fast, issues),
      verbosity: normalizeOneOf(
        raw.verbosity,
        "verbosity",
        VERBOSITY_VALUES,
        DEFAULT_CODEX_SETTINGS.verbosity,
        issues,
      ),
      reasoningSummary: normalizeOneOf(
        raw.reasoningSummary,
        "reasoningSummary",
        REASONING_SUMMARY_VALUES,
        DEFAULT_CODEX_SETTINGS.reasoningSummary,
        issues,
      ),
    },
    issues,
  };
}

function readCodexSettingsState(): CodexSettingsState {
  return normalizeCodexSettings(readSettingsRoot().codex);
}

function readSettingsRoot(): Record<string, unknown> {
  const settingsPath = getSettingsPath();
  if (!existsSync(settingsPath)) return {};

  const parsed: unknown = JSON.parse(readFileSync(settingsPath, "utf8"));
  return isObject(parsed) ? parsed : {};
}

function normalizeBoolean(
  value: unknown,
  key: keyof CodexSettings,
  fallback: boolean,
  issues: string[],
): boolean {
  if (value === undefined) return fallback;
  if (typeof value === "boolean") return value;

  issues.push(`settings.codex.${key} must be a boolean; using ${fallback}`);
  return fallback;
}

function normalizeOneOf<T extends string>(
  value: unknown,
  key: keyof CodexSettings,
  values: readonly T[],
  fallback: T,
  issues: string[],
): T {
  if (value === undefined) return fallback;
  if (typeof value !== "string") {
    issues.push(`settings.codex.${key} must be one of ${values.join(", ")}; using ${fallback}`);
    return fallback;
  }

  const normalized = value.trim().toLowerCase();
  if (values.includes(normalized as T)) return normalized as T;

  issues.push(`settings.codex.${key} must be one of ${values.join(", ")}; using ${fallback}`);
  return fallback;
}

function formatError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
