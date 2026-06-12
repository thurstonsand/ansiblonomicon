import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type { CompanionSession } from "./session.js";

export function registerCompanionCommand(pi: ExtensionAPI, session: CompanionSession): void {
  pi.registerCommand("companion", {
    description: "Toggle cursor companion (shows agent activity near cursor)",
    handler: async (_args, ctx) => {
      const note = "set glimpse.companion.enabled in settings to persist";
      if (session.isEnabled) {
        session.disable(ctx);
        ctx.ui.notify(`Companion disabled for this session (${note})`, "info");
      } else {
        await session.enable(ctx);
        if (session.isSupported) {
          ctx.ui.notify(`Companion enabled for this session (${note})`, "info");
        }
      }
    },
  });
}
