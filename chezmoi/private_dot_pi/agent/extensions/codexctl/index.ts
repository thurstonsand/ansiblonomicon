import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { getCodexArgumentCompletions, handleCodexCommand } from "./command.js";
import { applyCodexRequestSettings, shouldApplyCodexSettings } from "./request.js";
import { loadCodexSettingsState, startCodexSettingsWatcher } from "./settings.js";

export default function codexctl(pi: ExtensionAPI): void {
  startCodexSettingsWatcher();

  const notifyIssues = (ctx: ExtensionContext): void => {
    for (const issue of loadCodexSettingsState().issues) {
      ctx.ui.notify(issue, "error");
    }
  };

  pi.registerCommand("codex", {
    description: "Control Codex integration settings",
    getArgumentCompletions: getCodexArgumentCompletions,
    handler: handleCodexCommand,
  });

  pi.on("session_start", (_event, ctx) => notifyIssues(ctx));

  pi.on("before_provider_request", (event, ctx) => {
    if (!shouldApplyCodexSettings(ctx.model)) return undefined;
    const { settings } = loadCodexSettingsState();
    return applyCodexRequestSettings(event.payload, settings);
  });
}

export { applyCodexRequestSettings, shouldApplyCodexSettings } from "./request.js";
export { DEFAULT_CODEX_SETTINGS, normalizeCodexSettings } from "./settings.js";
