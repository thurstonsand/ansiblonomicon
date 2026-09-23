import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { ContextGaugeStatus } from "./context-gauge.js";
import { CostBudgetStatus } from "./cost-display.js";
import { ModelDisplayStatus } from "./model-display.js";
import { WorkspaceDisplayStatus } from "./workspace-display.js";

export default function powerlineFooterCustom(pi: ExtensionAPI): void {
  const contextGauge = new ContextGaugeStatus();
  const costBudget = new CostBudgetStatus();
  const modelDisplay = new ModelDisplayStatus();
  const workspaceDisplay = new WorkspaceDisplayStatus();

  pi.on("session_start", (event, ctx) => {
    contextGauge.sessionStart(event, ctx);
    costBudget.sessionStart(ctx);
    modelDisplay.sessionStart(ctx);
    workspaceDisplay.sessionStart(ctx);
  });

  pi.on("model_select", (_event, ctx) => {
    contextGauge.modelSelect(ctx);
    modelDisplay.modelSelect(ctx);
  });

  pi.on("thinking_level_select", (_event, ctx) => {
    modelDisplay.thinkingLevelSelect(ctx);
  });

  pi.on("session_tree", (_event, ctx) => {
    contextGauge.sessionTree(ctx);
    modelDisplay.sessionTree(ctx);
  });

  pi.on("turn_end", (_event, ctx) => {
    costBudget.turnEnd(ctx);
    workspaceDisplay.turnEnd(ctx);
  });

  pi.on("message_update", (event, ctx) => {
    contextGauge.messageUpdate(event, ctx);
  });

  pi.on("message_end", (_event, ctx) => {
    contextGauge.messageEnd(ctx);
  });

  pi.on("session_before_compact", (_event, ctx) => {
    contextGauge.sessionBeforeCompact(ctx);
  });

  pi.on("session_compact", (_event, ctx) => {
    contextGauge.sessionCompact(ctx);
  });

  pi.on("agent_settled", (_event, ctx) => {
    contextGauge.agentSettled(ctx);
  });

  pi.on("tool_result", (event, ctx) => {
    workspaceDisplay.toolResult(event, ctx);
  });

  pi.on("user_bash", (event, ctx) => {
    workspaceDisplay.userBash(event, ctx);
  });

  pi.on("session_shutdown", () => {
    contextGauge.sessionShutdown();
    costBudget.sessionShutdown();
    modelDisplay.sessionShutdown();
    workspaceDisplay.sessionShutdown();
  });

  pi.registerCommand("custom-footer-refresh", {
    description: "Refresh pi-powerline-footer-custom status items.",
    handler: async (_args, ctx) => {
      contextGauge.refresh(ctx);
      modelDisplay.refresh(ctx);
      await Promise.all([costBudget.refresh(ctx, true), workspaceDisplay.refresh(ctx, true)]);
      ctx.ui.notify("Custom footer statuses refreshed", "info");
    },
  });
}
