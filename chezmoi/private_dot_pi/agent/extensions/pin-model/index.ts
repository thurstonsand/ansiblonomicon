import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import type { Api, Model } from "@earendil-works/pi-ai";
import {
  type ExtensionAPI,
  type ExtensionCommandContext,
  getAgentDir,
} from "@earendil-works/pi-coding-agent";
import type { AutocompleteItem } from "@earendil-works/pi-tui";
import { fuzzyFilter } from "@earendil-works/pi-tui";
import lockfile from "proper-lockfile";

const RESTORE_DELAYS_MS = [300, 1_000, 3_000];
const THINKING_LEVELS = new Set<ThinkingLevel>([
  "off",
  "minimal",
  "low",
  "medium",
  "high",
  "xhigh",
  "max",
]);

export interface PinnedModel {
  provider: string;
  modelId: string;
  thinkingLevel: ThinkingLevel;
}

type SettingsDocument = Record<string, unknown>;
export type SettingsMutationResult = "changed" | "unchanged" | "failed";

function acquireSettingsLock(settingsPath: string): () => void {
  const maxAttempts = 10;
  const delayMs = 20;
  let lastError: unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return lockfile.lockSync(settingsPath, { realpath: false });
    } catch (error) {
      const code =
        typeof error === "object" && error !== null && "code" in error
          ? String((error as { code?: unknown }).code)
          : undefined;
      if (code !== "ELOCKED" || attempt === maxAttempts) throw error;
      lastError = error;
      const start = Date.now();
      while (Date.now() - start < delayMs) {}
    }
  }

  throw (lastError as Error) ?? new Error("Failed to acquire settings lock");
}

function mutateSettings(
  settingsPath: string,
  mutate: (settings: SettingsDocument) => boolean,
): SettingsMutationResult {
  if (!existsSync(settingsPath)) return "failed";

  let release: (() => void) | undefined;
  try {
    release = acquireSettingsLock(settingsPath);
    const parsed: unknown = JSON.parse(readFileSync(settingsPath, "utf8"));
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return "failed";

    const settings = parsed as SettingsDocument;
    if (!mutate(settings)) return "unchanged";
    writeFileSync(settingsPath, JSON.stringify(settings, null, 2), "utf8");
    return "changed";
  } catch {
    return "failed";
  } finally {
    try {
      release?.();
    } catch {}
  }
}

function isThinkingLevel(value: unknown): value is ThinkingLevel {
  return typeof value === "string" && THINKING_LEVELS.has(value as ThinkingLevel);
}

function readPinnedModel(value: unknown): PinnedModel | undefined {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return undefined;
  const candidate = value as Record<string, unknown>;
  if (
    typeof candidate.provider !== "string" ||
    typeof candidate.modelId !== "string" ||
    !isThinkingLevel(candidate.thinkingLevel)
  ) {
    return undefined;
  }

  return {
    provider: candidate.provider,
    modelId: candidate.modelId,
    thinkingLevel: candidate.thinkingLevel,
  };
}

function pinFromDefaults(settings: SettingsDocument): PinnedModel | undefined {
  if (
    typeof settings.defaultProvider !== "string" ||
    typeof settings.defaultModel !== "string" ||
    !isThinkingLevel(settings.defaultThinkingLevel)
  ) {
    return undefined;
  }

  return {
    provider: settings.defaultProvider,
    modelId: settings.defaultModel,
    thinkingLevel: settings.defaultThinkingLevel,
  };
}

export function restorePinnedDefaults(settingsPath: string): SettingsMutationResult {
  return mutateSettings(settingsPath, (settings) => {
    const existingPin = readPinnedModel(settings.pinnedModel);
    const pin = existingPin ?? pinFromDefaults(settings);
    if (!pin) return false;

    let changed = false;
    if (!existingPin) {
      settings.pinnedModel = pin;
      changed = true;
    }
    if (settings.defaultProvider !== pin.provider) {
      settings.defaultProvider = pin.provider;
      changed = true;
    }
    if (settings.defaultModel !== pin.modelId) {
      settings.defaultModel = pin.modelId;
      changed = true;
    }
    if (settings.defaultThinkingLevel !== pin.thinkingLevel) {
      settings.defaultThinkingLevel = pin.thinkingLevel;
      changed = true;
    }
    return changed;
  });
}

export function writePinnedDefaults(
  settingsPath: string,
  pin: PinnedModel,
): SettingsMutationResult {
  return mutateSettings(settingsPath, (settings) => {
    const existingPin = readPinnedModel(settings.pinnedModel);
    const unchanged =
      settings.defaultProvider === pin.provider &&
      settings.defaultModel === pin.modelId &&
      settings.defaultThinkingLevel === pin.thinkingLevel &&
      existingPin?.provider === pin.provider &&
      existingPin.modelId === pin.modelId &&
      existingPin.thinkingLevel === pin.thinkingLevel;
    if (unchanged) return false;

    settings.pinnedModel = pin;
    settings.defaultProvider = pin.provider;
    settings.defaultModel = pin.modelId;
    settings.defaultThinkingLevel = pin.thinkingLevel;
    return true;
  });
}

export function findExactModelReferenceMatch(
  modelReference: string,
  availableModels: Model<Api>[],
): Model<Api> | undefined {
  const trimmedReference = modelReference.trim();
  if (!trimmedReference) return undefined;

  const normalizedReference = trimmedReference.toLowerCase();
  const canonicalMatches = availableModels.filter(
    (model) => `${model.provider}/${model.id}`.toLowerCase() === normalizedReference,
  );
  if (canonicalMatches.length === 1) return canonicalMatches[0];
  if (canonicalMatches.length > 1) return undefined;

  const slashIndex = trimmedReference.indexOf("/");
  if (slashIndex !== -1) {
    const provider = trimmedReference.substring(0, slashIndex).trim();
    const modelId = trimmedReference.substring(slashIndex + 1).trim();
    if (provider && modelId) {
      const providerMatches = availableModels.filter(
        (model) =>
          model.provider.toLowerCase() === provider.toLowerCase() &&
          model.id.toLowerCase() === modelId.toLowerCase(),
      );
      if (providerMatches.length === 1) return providerMatches[0];
      if (providerMatches.length > 1) return undefined;
    }
  }

  const idMatches = availableModels.filter(
    (model) => model.id.toLowerCase() === normalizedReference,
  );
  return idMatches.length === 1 ? idMatches[0] : undefined;
}

function getModelSearchText(model: Model<Api>): string {
  const name = model.name ? ` ${model.name}` : "";
  return `${model.id} ${model.provider} ${model.provider}/${model.id} ${model.provider} ${model.id}${name}`;
}

function getModelSelectorSearchText(model: Model<Api>): string {
  const name = model.name ? ` ${model.name}` : "";
  return `${model.provider} ${model.provider}/${model.id} ${model.provider} ${model.id}${name}`;
}

function getArgumentCompletions(
  models: Model<Api>[],
  argumentPrefix: string,
): AutocompleteItem[] | null {
  const matches = fuzzyFilter(models, argumentPrefix, getModelSearchText);
  if (matches.length === 0) return null;
  return matches.map((model) => ({
    value: `${model.provider}/${model.id}`,
    label: model.id,
    description: model.provider,
  }));
}

async function pinModel(
  pi: ExtensionAPI,
  ctx: ExtensionCommandContext,
  settingsPath: string,
  model: Model<Api>,
  switchModel: boolean,
): Promise<void> {
  if (switchModel && !(await pi.setModel(model))) {
    ctx.ui.notify(`No API key for ${model.provider}/${model.id}`, "error");
    return;
  }

  const result = writePinnedDefaults(settingsPath, {
    provider: model.provider,
    modelId: model.id,
    thinkingLevel: pi.getThinkingLevel(),
  });
  if (result === "failed") {
    ctx.ui.notify("Could not update pinned model settings", "error");
    return;
  }

  ctx.ui.notify(`Model: ${model.id}`, "info");
}

export default function pinModelExtension(pi: ExtensionAPI): void {
  const settingsPath = join(getAgentDir(), "settings.json");
  let modelSource: (() => Model<Api>[]) | undefined;
  let restoreTimers: NodeJS.Timeout[] = [];

  const getAvailableModels = (): Model<Api>[] => {
    try {
      return modelSource?.() ?? [];
    } catch {
      return [];
    }
  };

  const clearRestoreTimers = (): void => {
    for (const timer of restoreTimers) clearTimeout(timer);
    restoreTimers = [];
  };

  const scheduleRestore = (): void => {
    clearRestoreTimers();
    restoreTimers = RESTORE_DELAYS_MS.map((delay) => {
      const timer = setTimeout(() => restorePinnedDefaults(settingsPath), delay);
      timer.unref();
      return timer;
    });
  };

  restorePinnedDefaults(settingsPath);

  pi.registerCommand("pin-model", {
    description: "Pin the default model and thinking level",
    getArgumentCompletions: (prefix) => getArgumentCompletions(getAvailableModels(), prefix),
    handler: async (args, ctx) => {
      const pattern = args.trim();
      if (!pattern) {
        if (!ctx.model) {
          ctx.ui.notify("No model is selected", "error");
          return;
        }
        await pinModel(pi, ctx, settingsPath, ctx.model, false);
        return;
      }

      ctx.modelRegistry.refresh();
      modelSource = () => ctx.modelRegistry.getAvailable();
      const availableModels = getAvailableModels();
      const exactMatch = findExactModelReferenceMatch(pattern, availableModels);
      if (exactMatch) {
        await pinModel(pi, ctx, settingsPath, exactMatch, true);
        return;
      }

      const partialMatches = fuzzyFilter(availableModels, pattern, getModelSelectorSearchText);
      if (partialMatches.length === 0) {
        ctx.ui.notify(`No models match "${pattern}"`, "error");
        return;
      }

      const references = partialMatches.map((model) => `${model.provider}/${model.id}`);
      const selected = await ctx.ui.select("Pin model:", references);
      if (!selected) return;
      const selectedModel = partialMatches[references.indexOf(selected)];
      if (selectedModel) await pinModel(pi, ctx, settingsPath, selectedModel, true);
    },
  });

  pi.on("session_start", (_event, ctx) => {
    restorePinnedDefaults(settingsPath);
    ctx.modelRegistry.refresh();
    modelSource = () => ctx.modelRegistry.getAvailable();
  });

  pi.on("model_select", scheduleRestore);
  pi.on("thinking_level_select", scheduleRestore);
  pi.on("session_shutdown", () => {
    clearRestoreTimers();
    restorePinnedDefaults(settingsPath);
  });
}
