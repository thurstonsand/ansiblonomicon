import path from "node:path";
import type { Api, Model } from "@mariozechner/pi-ai";
import { getAgentDir } from "@mariozechner/pi-coding-agent";

import { FileBackedStateWatcher } from "./file-backed-state-watcher.js";
import { readJsonFile } from "./json-file.js";

const FAST_CONFIG_BASENAME = "pi-openai-fast.json";
const FAST_CONFIG_PATH = path.join(getAgentDir(), "extensions", FAST_CONFIG_BASENAME);

type FastConfigFile = {
  active?: boolean;
  supportedModels?: string[];
};

export class FastStateWatcher extends FileBackedStateWatcher<FastConfigFile, boolean> {
  constructor(model: Model<Api>, onChange: (enabled: boolean) => void) {
    super(FAST_CONFIG_PATH, model, onChange);
  }

  protected readConfig(): FastConfigFile {
    const parsed = readJsonFile(FAST_CONFIG_PATH);
    if (!parsed) return {};

    const config: FastConfigFile = {};
    if (typeof parsed.active === "boolean") {
      config.active = parsed.active;
    }

    const supportedModels = this.normalizeSupportedModelKeys(parsed.supportedModels);
    if (supportedModels) {
      config.supportedModels = supportedModels;
    }
    return config;
  }

  protected project(config: FastConfigFile, model: Model<Api>): boolean {
    return (
      config.active === true && Boolean(config.supportedModels?.includes(this.modelKey(model)))
    );
  }

  private normalizeSupportedModelKeys(value: unknown): string[] | undefined {
    if (!Array.isArray(value)) return undefined;

    const normalized = value
      .filter((entry): entry is string => typeof entry === "string")
      .map((entry) => this.parseSupportedModelKey(entry))
      .filter((entry): entry is string => Boolean(entry));
    return normalized.length > 0 ? normalized : undefined;
  }

  private parseSupportedModelKey(value: string): string | undefined {
    const trimmed = value.trim();
    const slashIndex = trimmed.indexOf("/");
    if (slashIndex <= 0 || slashIndex >= trimmed.length - 1) return undefined;

    const provider = trimmed.slice(0, slashIndex).trim();
    const id = trimmed.slice(slashIndex + 1).trim();
    return provider && id ? `${provider}/${id}` : undefined;
  }

  private modelKey(model: Pick<Model<Api>, "provider" | "id">): string {
    return `${model.provider}/${model.id}`;
  }
}
