import { SettingsManager } from "@earendil-works/pi-coding-agent";
import { type Static, Type } from "typebox";
import type { ToolConfigOverrides } from "./activity.js";
import { parseTypeBoxValue } from "./typebox.js";

const TOOL_DETAIL_SCHEMA = Type.Object({
  from: Type.Optional(Type.Union([Type.String(), Type.Array(Type.String())])),
  transform: Type.Optional(Type.Literal("basename")),
});

const TOOL_CONFIG_SCHEMA = Type.Object({
  status: Type.Optional(Type.String()),
  detail: Type.Optional(TOOL_DETAIL_SCHEMA),
});

const COMPANION_SETTINGS_SCHEMA = Type.Object({
  enabled: Type.Optional(Type.Boolean()),
  tools: Type.Optional(Type.Record(Type.String(), TOOL_CONFIG_SCHEMA)),
});

const GLIMPSE_SETTINGS_SCHEMA = Type.Object({
  companion: Type.Optional(COMPANION_SETTINGS_SCHEMA),
});

const ROOT_SETTINGS_SCHEMA = Type.Object({
  glimpse: Type.Optional(GLIMPSE_SETTINGS_SCHEMA),
});

type CompanionFileSettings = Static<typeof COMPANION_SETTINGS_SCHEMA>;

function loadCompanionFileSettings(): CompanionFileSettings {
  const globalSettings = SettingsManager.create(process.cwd()).getGlobalSettings();
  const parsed = parseTypeBoxValue(ROOT_SETTINGS_SCHEMA, globalSettings, "Invalid settings");
  return parsed.glimpse?.companion ?? {};
}

/**
 * The centralized companion settings (`glimpse.companion.*`), parsed once.
 * Callers read whichever field they need rather than re-parsing the settings
 * tree. `enabled` is the persisted default; SettingsManager is read-only, so the
 * `/companion` toggle only affects the live session.
 */
export interface CompanionSettings {
  enabled: boolean;
  tools: ToolConfigOverrides;
}

export function loadCompanionSettings(): CompanionSettings {
  const file = loadCompanionFileSettings();
  return {
    enabled: file.enabled === true,
    tools: file.tools ?? {},
  };
}
