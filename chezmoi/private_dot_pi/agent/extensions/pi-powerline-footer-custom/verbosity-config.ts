import path from "node:path";
import type { Api, Model } from "@mariozechner/pi-ai";
import { getAgentDir } from "@mariozechner/pi-coding-agent";

import { FileBackedStateWatcher } from "./file-backed-state-watcher.js";
import { isJsonObject, readJsonFile } from "./json-file.js";

const VERBOSITY_CONFIG_PATH = path.join(getAgentDir(), "verbosity.json");
const VERBOSITY_LEVELS = ["low", "medium", "high"] as const;
const VERBOSITY_LEVEL_SET: ReadonlySet<string> = new Set(VERBOSITY_LEVELS);

export type Verbosity = (typeof VERBOSITY_LEVELS)[number];
type VerbosityConfig = Record<string, Verbosity>;

export const VERBOSITY_ICONS: Record<Verbosity, string> = {
  high: "●",
  medium: "◐",
  low: "◔",
};

export class VerbosityStateWatcher extends FileBackedStateWatcher<
  VerbosityConfig,
  Verbosity | undefined
> {
  constructor(model: Model<Api>, onChange: (verbosity: Verbosity | undefined) => void) {
    super(VERBOSITY_CONFIG_PATH, model, onChange);
  }

  protected readConfig(): VerbosityConfig {
    const parsed = readJsonFile(VERBOSITY_CONFIG_PATH);
    const models = parsed?.models;
    if (!isJsonObject(models)) return {};

    const config: VerbosityConfig = {};
    for (const [key, value] of Object.entries(models)) {
      const verbosity = this.normalizeVerbosity(value);
      if (verbosity) config[key] = verbosity;
    }
    return config;
  }

  protected project(config: VerbosityConfig, model: Model<Api>): Verbosity | undefined {
    const exactKey = `${model.provider}/${model.id}`;
    return config[exactKey] ?? config[model.id];
  }

  private normalizeVerbosity(value: unknown): Verbosity | undefined {
    if (typeof value !== "string") return undefined;

    const normalized = value.trim().toLowerCase();
    return VERBOSITY_LEVEL_SET.has(normalized) ? (normalized as Verbosity) : undefined;
  }
}
