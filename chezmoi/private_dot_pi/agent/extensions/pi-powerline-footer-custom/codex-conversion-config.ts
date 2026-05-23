import path from "node:path";
import type { Api, Model } from "@earendil-works/pi-ai";
import { getAgentDir } from "@earendil-works/pi-coding-agent";

import { FileBackedStateWatcher, type Eq } from "./file-backed-state-watcher.js";
import { readJsonFile } from "./json-file.js";

type CodexVerbosity = "low" | "medium" | "high";

type CodexConversionConfigFile = {
  fast?: boolean;
  verbosity?: CodexVerbosity;
};

export type CodexConversionStatus = {
  fast: boolean;
  verbosity?: CodexVerbosity;
};

const codexConversionStatusEq: Eq<CodexConversionStatus> = (self, that) =>
  self.fast === that.fast && self.verbosity === that.verbosity;

export class CodexConversionConfigWatcher extends FileBackedStateWatcher<
  CodexConversionConfigFile,
  CodexConversionStatus
> {
  private static readonly configPath = path.join(getAgentDir(), "pi-codex-conversion.json");
  private static readonly verbosityLevels: ReadonlySet<string> = new Set(["low", "medium", "high"]);

  constructor(model: Model<Api>, onChange: (status: CodexConversionStatus) => void) {
    super(
      CodexConversionConfigWatcher.configPath,
      model,
      onChange,
      codexConversionStatusEq,
    );
  }

  protected readConfig(): CodexConversionConfigFile {
    const parsed = readJsonFile(CodexConversionConfigWatcher.configPath);
    return {
      fast: typeof parsed?.fast === "boolean" ? parsed.fast : undefined,
      verbosity: CodexConversionConfigWatcher.normalizeVerbosity(parsed?.verbosity),
    };
  }

  protected project(config: CodexConversionConfigFile, model: Model<Api>): CodexConversionStatus {
    if (model.provider !== "openai-codex") return { fast: false };
    return {
      fast: config.fast === true,
      verbosity: config.verbosity,
    };
  }

  private static normalizeVerbosity(value: unknown): CodexVerbosity | undefined {
    if (typeof value !== "string") return undefined;

    const normalized = value.trim().toLowerCase();
    return CodexConversionConfigWatcher.verbosityLevels.has(normalized)
      ? (normalized as CodexVerbosity)
      : undefined;
  }
}
