import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { registerCompanionCommand } from "./companion/command.js";
import { registerCompanionHandlers } from "./companion/handlers.js";
import { CompanionSession } from "./companion/session.js";

export default function companionExtension(pi: ExtensionAPI): void {
  const session = new CompanionSession();
  registerCompanionCommand(pi, session);
  registerCompanionHandlers(pi, session);
}
