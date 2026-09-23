import { getAgentDir, SettingsManager } from "@earendil-works/pi-coding-agent";
import { type Static, Type } from "typebox";

import { parseTypeBoxValue } from "./typebox.js";

const BUDGET_SETTINGS_SCHEMA = Type.Object({
  url: Type.Optional(Type.String()),
  costsUrl: Type.Optional(Type.String()),
});

const JIRA_SETTINGS_SCHEMA = Type.Object({
  browseUrl: Type.Optional(Type.String()),
});

const POWERLINE_CUSTOM_SCHEMA = Type.Object({
  budget: Type.Optional(BUDGET_SETTINGS_SCHEMA),
  jira: Type.Optional(JIRA_SETTINGS_SCHEMA),
});

const ROOT_SETTINGS_SCHEMA = Type.Object({
  powerlineCustom: Type.Optional(POWERLINE_CUSTOM_SCHEMA),
});

export type BudgetSettings = Static<typeof BUDGET_SETTINGS_SCHEMA>;
export type JiraSettings = Static<typeof JIRA_SETTINGS_SCHEMA>;

let cached: Static<typeof POWERLINE_CUSTOM_SCHEMA> | undefined;

function load(): Static<typeof POWERLINE_CUSTOM_SCHEMA> {
  if (cached) return cached;
  const global = SettingsManager.create(process.cwd(), getAgentDir()).getGlobalSettings();
  cached =
    parseTypeBoxValue(ROOT_SETTINGS_SCHEMA, global, "Invalid powerlineCustom settings")
      .powerlineCustom ?? {};
  return cached;
}

export function getBudgetSettings(): BudgetSettings {
  return load().budget ?? {};
}

export function getJiraSettings(): JiraSettings {
  return load().jira ?? {};
}

/**
 * Native pi compaction reserve, re-exposed here so the custom segments read all
 * settings through one module. Read live (not memoized) since it is not part of
 * the powerlineCustom block.
 */
export function getCompactionReserveTokens(cwd: string): number {
  return SettingsManager.create(cwd, getAgentDir()).getCompactionReserveTokens();
}
