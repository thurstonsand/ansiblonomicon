import type { Theme } from "@mariozechner/pi-coding-agent";

import {
  VERBOSITY_CONFIG_PATH,
  VERBOSITY_LEVELS,
  type ModelSegmentOptions,
  type Verbosity,
  type VerbosityConfig,
  type VerbosityStyle,
} from "./constants.js";
import { applyColor } from "./theme.js";
import { createFileWatcher } from "./watcher.js";

let cachedVerbosityConfig: VerbosityConfig = {};

function normalizeVerbosity(value: unknown): Verbosity | undefined {
  if (typeof value !== "string") {
    return undefined;
  }

  const normalized = value.trim().toLowerCase();
  return VERBOSITY_LEVELS.includes(normalized as Verbosity)
    ? normalized as Verbosity
    : undefined;
}

function reloadVerbosityConfig(contents: string | undefined): void {
  try {
    if (!contents) {
      cachedVerbosityConfig = {};
      return;
    }

    const parsed = JSON.parse(contents);
    const models = parsed && typeof parsed === "object" && !Array.isArray(parsed) && parsed.models && typeof parsed.models === "object" && !Array.isArray(parsed.models)
      ? parsed.models
      : {};

    const normalized: VerbosityConfig = {};
    for (const [key, value] of Object.entries(models)) {
      const normalizedKey = key.trim();
      const normalizedValue = normalizeVerbosity(value);
      if (!normalizedKey || !normalizedValue) {
        continue;
      }
      normalized[normalizedKey] = normalizedValue;
    }

    cachedVerbosityConfig = normalized;
  } catch {
    cachedVerbosityConfig = {};
  }
}

const ensureWatcher = createFileWatcher(VERBOSITY_CONFIG_PATH, (files) => {
  reloadVerbosityConfig(files.get(VERBOSITY_CONFIG_PATH));
});

export function resolveVerbosity(model: { provider?: string; id?: string } | undefined): Verbosity | undefined {
  if (!model?.id) {
    return undefined;
  }

  ensureWatcher();
  const exactKey = model.provider ? `${model.provider}/${model.id}` : undefined;
  if (exactKey && cachedVerbosityConfig[exactKey]) {
    return cachedVerbosityConfig[exactKey];
  }

  return cachedVerbosityConfig[model.id];
}

export function getVerbosityStyle(options: ModelSegmentOptions | undefined): VerbosityStyle {
  return options?.verbosity?.style ?? "compact";
}

export function formatVerbosity(level: Verbosity, style: VerbosityStyle): string {
  switch (style) {
    case "labelled":
      return `verbosity:${level}`;
    case "icon":
      return `🗣 ${level}`;
    default:
      return `verb:${level}`;
  }
}

export function colorForVerbosity(theme: Theme | undefined, level: Verbosity, text: string): string {
  if (level === "high") {
    return applyColor(theme, "warning", text);
  }

  if (level === "medium") {
    return applyColor(theme, "accent", text);
  }

  return applyColor(theme, "muted", text);
}
