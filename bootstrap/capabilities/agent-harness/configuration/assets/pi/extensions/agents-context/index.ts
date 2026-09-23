import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { contextFileKind } from "./detect.js";
import { collectContextFiles } from "./load.js";
import { renderBlocks } from "./render.js";
import { type AgentsContextSettings, loadSettings } from "./settings.js";

export default function agentsContext(pi: ExtensionAPI): void {
  let settings: AgentsContextSettings | undefined;

  pi.on("before_agent_start", (event, ctx) => {
    settings ??= loadSettings(ctx.cwd);

    const contextFiles = event.systemPromptOptions.contextFiles ?? [];
    const rootContextFiles = contextFiles.filter((file) => contextFileKind(file.path));
    if (rootContextFiles.length === 0) return;

    const loaded = collectContextFiles(rootContextFiles, contextFiles, settings.maxDepth, ctx.ui);
    if (loaded.length === 0) return;

    return { systemPrompt: event.systemPrompt + renderBlocks(loaded) };
  });
}
