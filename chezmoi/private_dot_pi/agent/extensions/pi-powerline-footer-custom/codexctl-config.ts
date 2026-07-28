import path from "node:path";
import type { Api, Model } from "@earendil-works/pi-ai";
import { getAgentDir } from "@earendil-works/pi-coding-agent";

import { shouldApplyCodexSettings } from "../codexctl/request.js";
import {
  type CodexReasoningSummary,
  type CodexVerbosity,
  REASONING_SUMMARY_VALUES,
  VERBOSITY_VALUES,
} from "../codexctl/settings.js";
import { type Eq, FileBackedStateWatcher } from "./file-backed-state-watcher.js";
import { isJsonObject, readJsonFile } from "./json-file.js";

type PiSettingsFile = {
  codex?: {
    fast?: boolean;
    verbosity?: CodexVerbosity;
    reasoningSummary?: CodexReasoningSummary;
  };
};

export type CodexStatus = {
  fast: boolean;
  verbosity?: CodexVerbosity;
  reasoningSummary?: CodexReasoningSummary;
};

const codexStatusEq: Eq<CodexStatus> = (self, that) =>
  self.fast === that.fast &&
  self.verbosity === that.verbosity &&
  self.reasoningSummary === that.reasoningSummary;

export class CodexConfigWatcher extends FileBackedStateWatcher<PiSettingsFile, CodexStatus> {
  private static readonly settingsPath = path.join(getAgentDir(), "settings.json");
  private static readonly verbosityLevels: ReadonlySet<string> = new Set(VERBOSITY_VALUES);
  private static readonly reasoningSummaryValues: ReadonlySet<string> = new Set(
    REASONING_SUMMARY_VALUES,
  );

  constructor(model: Model<Api>, onChange: (status: CodexStatus) => void) {
    super(CodexConfigWatcher.settingsPath, model, onChange, codexStatusEq);
  }

  protected readConfig(): PiSettingsFile {
    const parsed = readJsonFile(CodexConfigWatcher.settingsPath);
    const codex = isJsonObject(parsed?.codex) ? parsed.codex : undefined;
    return {
      codex: codex
        ? {
            fast: typeof codex.fast === "boolean" ? codex.fast : undefined,
            verbosity: CodexConfigWatcher.normalizeVerbosity(codex.verbosity),
            reasoningSummary: CodexConfigWatcher.normalizeReasoningSummary(codex.reasoningSummary),
          }
        : undefined,
    };
  }

  protected project(config: PiSettingsFile, model: Model<Api>): CodexStatus {
    if (!shouldApplyCodexSettings(model)) return { fast: false };
    return {
      fast: config.codex?.fast === true,
      verbosity: config.codex?.verbosity,
      reasoningSummary: config.codex?.reasoningSummary,
    };
  }

  private static normalizeVerbosity(value: unknown): CodexVerbosity | undefined {
    if (typeof value !== "string") return undefined;

    const normalized = value.trim().toLowerCase();
    return CodexConfigWatcher.verbosityLevels.has(normalized)
      ? (normalized as CodexVerbosity)
      : undefined;
  }

  private static normalizeReasoningSummary(value: unknown): CodexReasoningSummary | undefined {
    if (typeof value !== "string") return undefined;

    const normalized = value.trim().toLowerCase();
    return CodexConfigWatcher.reasoningSummaryValues.has(normalized)
      ? (normalized as CodexReasoningSummary)
      : undefined;
  }
}
