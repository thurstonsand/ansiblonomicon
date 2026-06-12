import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { isAgentsFile } from "./detect.js";
import { collectReferences } from "./load.js";
import { renderBlock } from "./render.js";
import { type AgentsContextSettings, loadSettings } from "./settings.js";

export default function agentsContext(pi: ExtensionAPI): void {
  let settings: AgentsContextSettings | undefined;

  pi.on("before_agent_start", (event, ctx) => {
    settings ??= loadSettings(ctx.cwd);

    const contextFiles = event.systemPromptOptions.contextFiles ?? [];
    const agentsFiles = contextFiles.filter((file) => isAgentsFile(file.path));
    if (agentsFiles.length === 0) return;

    const loaded = collectReferences(agentsFiles, contextFiles, settings.maxDepth, ctx.ui);
    if (loaded.length === 0) return;

    return { systemPrompt: event.systemPrompt + renderBlock(loaded) };
  });
}
