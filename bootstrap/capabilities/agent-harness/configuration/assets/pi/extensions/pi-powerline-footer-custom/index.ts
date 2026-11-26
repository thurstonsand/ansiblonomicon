import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

import { ContextGaugeStatus } from "./context-gauge.js";
import { CostBudgetStatus } from "./cost-display.js";
import { ModelDisplayStatus } from "./model-display.js";
import { WorkspaceDisplayStatus } from "./workspace-display.js";

/**
 * Model, workspace and context items only feed the TUI footer. An RPC host
 * shows every status in one line and already shows those natively, so only
 * the budget, which no host shows, is published there.
 */
function rendersFooter(ctx: ExtensionContext): boolean {
  return ctx.mode === "tui";
}

export default function powerlineFooterCustom(pi: ExtensionAPI): void {
  const contextGauge = new ContextGaugeStatus();
  const costBudget = new CostBudgetStatus();
  const modelDisplay = new ModelDisplayStatus();
  const workspaceDisplay = new WorkspaceDisplayStatus();

  pi.on("session_start", (event, ctx) => {
    costBudget.sessionStart(ctx);
    if (!rendersFooter(ctx)) return;
    contextGauge.sessionStart(event, ctx);
    modelDisplay.sessionStart(ctx);
    workspaceDisplay.sessionStart(ctx);
  });

  pi.on("model_select", (_event, ctx) => {
    if (!rendersFooter(ctx)) return;
    contextGauge.modelSelect(ctx);
    modelDisplay.modelSelect(ctx);
  });

  pi.on("thinking_level_select", (_event, ctx) => {
    if (!rendersFooter(ctx)) return;
    modelDisplay.thinkingLevelSelect(ctx);
  });

  pi.on("session_tree", (_event, ctx) => {
    if (!rendersFooter(ctx)) return;
    contextGauge.sessionTree(ctx);
    modelDisplay.sessionTree(ctx);
  });

  pi.on("turn_end", (_event, ctx) => {
    costBudget.turnEnd(ctx);
    if (!rendersFooter(ctx)) return;
    workspaceDisplay.turnEnd(ctx);
  });

  pi.on("message_update", (event, ctx) => {
    if (!rendersFooter(ctx)) return;
    contextGauge.messageUpdate(event, ctx);
  });

  pi.on("message_end", (_event, ctx) => {
    if (!rendersFooter(ctx)) return;
    contextGauge.messageEnd(ctx);
  });

  pi.on("session_before_compact", (_event, ctx) => {
    if (!rendersFooter(ctx)) return;
    contextGauge.sessionBeforeCompact(ctx);
  });

  pi.on("session_compact", (_event, ctx) => {
    if (!rendersFooter(ctx)) return;
    contextGauge.sessionCompact(ctx);
  });

  pi.on("agent_settled", (_event, ctx) => {
    if (!rendersFooter(ctx)) return;
    contextGauge.agentSettled(ctx);
  });

  pi.on("tool_result", (event, ctx) => {
    if (!rendersFooter(ctx)) return;
    workspaceDisplay.toolResult(event, ctx);
  });

  pi.on("user_bash", (event, ctx) => {
    if (!rendersFooter(ctx)) return;
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
      if (rendersFooter(ctx)) {
        contextGauge.refresh(ctx);
        modelDisplay.refresh(ctx);
        await Promise.all([costBudget.refresh(ctx, true), workspaceDisplay.refresh(ctx, true)]);
      } else {
        await costBudget.refresh(ctx, true);
      }
      ctx.ui.notify("Custom footer statuses refreshed", "info");
    },
  });
}
