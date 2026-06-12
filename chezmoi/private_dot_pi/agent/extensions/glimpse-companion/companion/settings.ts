import { SettingsManager } from "@earendil-works/pi-coding-agent";
import { type Static, Type } from "typebox";
import { parseTypeBoxValue } from "./typebox.js";

const COMPANION_SETTINGS_SCHEMA = Type.Object({
  enabled: Type.Optional(Type.Boolean()),
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
 * The configured default from the pi settings file (`glimpse.companion.enabled`).
 * SettingsManager is read-only, so the `/companion` toggle only affects the live
 * session; permanent changes are made by editing the settings file.
 */
export function loadEnabled(): boolean {
  return loadCompanionFileSettings().enabled === true;
}
