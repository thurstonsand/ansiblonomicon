import path from "node:path";
import type { Theme } from "@mariozechner/pi-coding-agent";

import {
  FAST_CONFIG_BASENAME,
  FAST_CONFIG_PATH,
  type FastConfig,
  type FastConfigFile,
  type FastStyle,
  type ModelSegmentOptions,
} from "./constants.js";
import { applyColor, getFastIcon, withIcon } from "./theme.js";
import { createFileWatcher } from "./watcher.js";

let cachedFastConfig: FastConfig = {
  active: false,
  supportedModels: new Set<string>(),
};

function normalizeSupportedModelKey(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }

  const trimmed = value.trim();
  const slashIndex = trimmed.indexOf("/");
  if (slashIndex <= 0 || slashIndex >= trimmed.length - 1) {
    return undefined;
  }

  const provider = trimmed.slice(0, slashIndex).trim();
  const id = trimmed.slice(slashIndex + 1).trim();
  if (!provider || !id) {
    return undefined;
  }

  return `${provider}/${id}`;
}

function parseFastConfigFile(contents: string | undefined): FastConfigFile {
  try {
    if (!contents) {
      return {};
    }

    const parsed = JSON.parse(contents);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }

    const config: FastConfigFile = {};
    if (typeof parsed.active === "boolean") {
      config.active = parsed.active;
    }

    if (Array.isArray(parsed.supportedModels)) {
      config.supportedModels = parsed.supportedModels
        .map((value) => normalizeSupportedModelKey(value))
        .filter((value): value is string => Boolean(value));
    }

    return config;
  } catch {
    return {};
  }
}

const PROJECT_FAST_CONFIG_PATH = path.join(process.cwd(), ".pi", "extensions", FAST_CONFIG_BASENAME);

const ensureWatcher = createFileWatcher([FAST_CONFIG_PATH, PROJECT_FAST_CONFIG_PATH], (files) => {
  const globalConfig = parseFastConfigFile(files.get(FAST_CONFIG_PATH));
  const projectConfig = parseFastConfigFile(files.get(PROJECT_FAST_CONFIG_PATH));
  const merged = {
    ...globalConfig,
    ...projectConfig,
  };

  cachedFastConfig = {
    active: merged.active === true,
    supportedModels: new Set(merged.supportedModels ?? []),
  };
});

export function isFastEnabled(model: { provider?: string; id?: string } | undefined): boolean {
  if (!model?.provider || !model.id) {
    return false;
  }

  ensureWatcher();
  return cachedFastConfig.active && cachedFastConfig.supportedModels.has(`${model.provider}/${model.id}`);
}

export function getFastStyle(options: ModelSegmentOptions | undefined): FastStyle {
  return options?.fast?.style ?? "icon";
}

export function formatFast(style: FastStyle): string {
  switch (style) {
    case "icon":
      return getFastIcon();
    case "text":
      return "fast";
    default:
      return withIcon(getFastIcon(), "fast");
  }
}

export function colorForFast(theme: Theme | undefined, text: string): string {
  return applyColor(theme, "success", text);
}
