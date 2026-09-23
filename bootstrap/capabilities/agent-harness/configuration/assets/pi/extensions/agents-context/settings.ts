import { SettingsManager } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { Value } from "typebox/value";

export const DEFAULT_MAX_DEPTH = 5;

const SETTINGS_SCHEMA = Type.Object({
  agentsContext: Type.Optional(
    Type.Object({
      maxDepth: Type.Optional(Type.Integer({ minimum: 1 })),
    }),
  ),
});

export interface AgentsContextSettings {
  maxDepth: number;
}

/** Resolve agentsContext settings from global settings, applying defaults. */
export function loadSettings(cwd: string): AgentsContextSettings {
  let raw: { maxDepth?: number } | undefined;
  try {
    const settings = SettingsManager.create(cwd).getGlobalSettings();
    if (Value.Check(SETTINGS_SCHEMA, settings)) {
      raw = settings.agentsContext;
    }
  } catch {
    // fall through to defaults
  }

  return {
    maxDepth: raw?.maxDepth ?? DEFAULT_MAX_DEPTH,
  };
}
