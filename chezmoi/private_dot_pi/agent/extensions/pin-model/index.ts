import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import { getSupportedThinkingLevels } from "@earendil-works/pi-ai";
import {
  type ExtensionAPI,
  type ExtensionCommandContext,
  type ExtensionContext,
  getAgentDir,
  type ScopedModel,
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
  availableModels: readonly ScopedModel[],
): ScopedModel | undefined {
  const trimmedReference = modelReference.trim();
  if (!trimmedReference) return undefined;

  const normalizedReference = trimmedReference.toLowerCase();
  const canonicalMatches = availableModels.filter(
    ({ model }) => `${model.provider}/${model.id}`.toLowerCase() === normalizedReference,
  );
  if (canonicalMatches.length === 1) return canonicalMatches[0];
  if (canonicalMatches.length > 1) return undefined;

  const slashIndex = trimmedReference.indexOf("/");
  if (slashIndex !== -1) {
    const provider = trimmedReference.substring(0, slashIndex).trim();
    const modelId = trimmedReference.substring(slashIndex + 1).trim();
    if (provider && modelId) {
      const providerMatches = availableModels.filter(
        ({ model }) =>
          model.provider.toLowerCase() === provider.toLowerCase() &&
          model.id.toLowerCase() === modelId.toLowerCase(),
      );
      if (providerMatches.length === 1) return providerMatches[0];
      if (providerMatches.length > 1) return undefined;
    }
  }

  const idMatches = availableModels.filter(
    ({ model }) => model.id.toLowerCase() === normalizedReference,
  );
  return idMatches.length === 1 ? idMatches[0] : undefined;
}

export interface ModelArgument {
  reference: string;
  thinkingLevel?: ThinkingLevel;
}

/**
 * Split a `model[:level]` argument. Model ids carry their own colons (Bedrock's
 * `...-v1:0`), so a suffix is only a thinking level when it actually names one.
 */
export function parseModelArgument(argument: string): ModelArgument {
  const separator = argument.lastIndexOf(":");
  if (separator === -1) return { reference: argument.trim() };

  const suffix = argument.slice(separator + 1).trim();
  if (!isThinkingLevel(suffix)) return { reference: argument.trim() };

  return { reference: argument.slice(0, separator).trim(), thinkingLevel: suffix };
}

// Pi's own selector and cycler operate on the scoped models, so pinning outside
// that scope would write a default the built-in selector never offers. An empty
// scope means no scoping is configured, leaving the whole catalogue usable.
function selectableModels(ctx: ExtensionContext): ScopedModel[] {
  return ctx.scopedModels.length > 0
    ? [...ctx.scopedModels]
    : ctx.modelRegistry.getAvailable().map((model) => ({ model }));
}

function modelReference({ model, thinkingLevel }: ScopedModel): string {
  const reference = `${model.provider}/${model.id}`;
  return thinkingLevel ? `${reference}:${thinkingLevel}` : reference;
}

function getModelSearchText({ model }: ScopedModel): string {
  const name = model.name ? ` ${model.name}` : "";
  return `${model.id} ${model.provider} ${model.provider}/${model.id} ${model.provider} ${model.id}${name}`;
}

function getModelSelectorSearchText({ model }: ScopedModel): string {
  const name = model.name ? ` ${model.name}` : "";
  return `${model.provider} ${model.provider}/${model.id} ${model.provider} ${model.id}${name}`;
}

function getThinkingLevelCompletions(
  scoped: ScopedModel,
  levelPrefix: string,
): AutocompleteItem[] | null {
  const reference = `${scoped.model.provider}/${scoped.model.id}`;
  const levels = getSupportedThinkingLevels(scoped.model).filter((level) =>
    level.startsWith(levelPrefix.toLowerCase()),
  );
  if (levels.length === 0) return null;

  return levels.map((level) => ({
    value: `${reference}:${level}`,
    label: level,
    description: scoped.model.id,
  }));
}

function getArgumentCompletions(
  models: readonly ScopedModel[],
  argumentPrefix: string,
): AutocompleteItem[] | null {
  // An exact model on the left of a colon means the user is choosing a level for
  // it. Anything else — including a model id whose own suffix is `:0` — is still
  // a model reference being typed.
  const separator = argumentPrefix.lastIndexOf(":");
  if (separator !== -1) {
    const match = findExactModelReferenceMatch(argumentPrefix.slice(0, separator), models);
    if (match)
      return getThinkingLevelCompletions(match, argumentPrefix.slice(separator + 1).trim());
  }

  const matches = fuzzyFilter([...models], argumentPrefix, getModelSearchText);
  if (matches.length === 0) return null;
  return matches.map((scoped) => ({
    value: modelReference(scoped),
    label: scoped.thinkingLevel ? `${scoped.model.id}:${scoped.thinkingLevel}` : scoped.model.id,
    description: scoped.model.provider,
  }));
}

/**
 * Switching models mirrors pi's own cycler: an explicitly requested level wins,
 * else the level the scope pinned, else whatever the session already sits at.
 * Pinning in place (no switch) always keeps the current level, since the point
 * of a bare `/pin-model` is to capture where you already are.
 */
async function pinModel(
  pi: ExtensionAPI,
  ctx: ExtensionCommandContext,
  settingsPath: string,
  scoped: ScopedModel,
  requestedLevel: ThinkingLevel | undefined,
  switchModel: boolean,
): Promise<void> {
  const { model } = scoped;

  if (requestedLevel && !getSupportedThinkingLevels(model).includes(requestedLevel)) {
    const supported = getSupportedThinkingLevels(model).join(", ");
    ctx.ui.notify(`${model.id} supports only: ${supported}`, "error");
    return;
  }

  if (switchModel && !(await pi.setModel(model))) {
    ctx.ui.notify(`No API key for ${model.provider}/${model.id}`, "error");
    return;
  }

  const thinkingLevel = switchModel ? (requestedLevel ?? scoped.thinkingLevel) : requestedLevel;
  if (thinkingLevel) pi.setThinkingLevel(thinkingLevel);

  // Read back rather than reusing the requested level: pi clamps to what the
  // model actually supports, and that clamped value is what the session runs on.
  const effectiveLevel = pi.getThinkingLevel();
  const result = writePinnedDefaults(settingsPath, {
    provider: model.provider,
    modelId: model.id,
    thinkingLevel: effectiveLevel,
  });
  if (result === "failed") {
    ctx.ui.notify("Could not update pinned model settings", "error");
    return;
  }

  ctx.ui.notify(`Model: ${model.id} (${effectiveLevel})`, "info");
}

export default function pinModelExtension(pi: ExtensionAPI): void {
  const settingsPath = join(getAgentDir(), "settings.json");
  let modelSource: (() => ScopedModel[]) | undefined;
  let restoreTimers: NodeJS.Timeout[] = [];

  const getAvailableModels = (): ScopedModel[] => {
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
      const { reference, thinkingLevel } = parseModelArgument(args);
      modelSource = () => selectableModels(ctx);
      const availableModels = getAvailableModels();

      if (!reference) {
        if (!ctx.model) {
          ctx.ui.notify("No model is selected", "error");
          return;
        }
        await pinModel(pi, ctx, settingsPath, { model: ctx.model }, thinkingLevel, false);
        return;
      }

      const exactMatch = findExactModelReferenceMatch(reference, availableModels);
      if (exactMatch) {
        await pinModel(pi, ctx, settingsPath, exactMatch, thinkingLevel, true);
        return;
      }

      const partialMatches = fuzzyFilter(availableModels, reference, getModelSelectorSearchText);
      if (partialMatches.length === 0) {
        ctx.ui.notify(`No models match "${reference}"`, "error");
        return;
      }

      const references = partialMatches.map(modelReference);
      const selected = await ctx.ui.select("Pin model:", references);
      if (!selected) return;
      const selectedModel = partialMatches[references.indexOf(selected)];
      if (selectedModel) await pinModel(pi, ctx, settingsPath, selectedModel, thinkingLevel, true);
    },
  });

  // Read the registry, never refresh it. Pi populates it before extensions bind and
  // re-refreshes on every credential change, so this handler exists only to capture ctx
  // for the argument completions. Even a bounded refresh is redundant here, and pi awaits
  // session_start handlers in series, so it would delay every extension loaded after this one.
  pi.on("session_start", (_event, ctx) => {
    restorePinnedDefaults(settingsPath);
    modelSource = () => selectableModels(ctx);
  });

  pi.on("model_select", scheduleRestore);
  pi.on("thinking_level_select", scheduleRestore);
  pi.on("session_shutdown", () => {
    clearRestoreTimers();
    restorePinnedDefaults(settingsPath);
  });
}
