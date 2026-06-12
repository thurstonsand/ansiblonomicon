import type { Api, Model } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { CodexConfigWatcher } from "./codexctl-config.js";
import { ContextGaugeStatus } from "./context-gauge.js";
import { CostBudgetStatus } from "./cost-display.js";
import { DebouncedTask } from "./debounced-task.js";
import { updateModelDisplayStatus } from "./model-display.js";
import { updateWorkspaceDisplayStatuses } from "./workspace-display.js";

const CONTEXT_STATUS_UPDATE_MS = 250;

export default function powerlineFooterCustom(pi: ExtensionAPI): void {
  let contextGaugeStatus: ContextGaugeStatus | undefined;
  let costBudgetStatus: CostBudgetStatus | undefined;
  let codexWatcher: CodexConfigWatcher | undefined;
  let modelDisplayDirty = false;

  const contextGaugeSetTask = new DebouncedTask<ExtensionContext>(CONTEXT_STATUS_UPDATE_MS, (ctx) =>
    contextGaugeStatus?.update(ctx),
  );

  const setModelDisplay = (ctx: ExtensionContext): void => {
    updateModelDisplayStatus(ctx, pi.getThinkingLevel(), codexWatcher?.get());
    modelDisplayDirty = false;
  };

  const setModelDisplayIfDirty = (ctx: ExtensionContext): void => {
    if (modelDisplayDirty) setModelDisplay(ctx);
  };

  const setContextGauge = (ctx: ExtensionContext): void => {
    contextGaugeSetTask.flush(ctx);
  };

  const setCustomFooter = (ctx: ExtensionContext): void => {
    setContextGauge(ctx);
    setModelDisplay(ctx);
    void costBudgetStatus?.update(ctx);
    updateWorkspaceDisplayStatuses(ctx);
  };

  const refreshCostBudget = (ctx: ExtensionContext): void => {
    void costBudgetStatus?.update(ctx);
  };

  const setModel = (ctx: ExtensionContext): void => {
    const model = requireModel(ctx);
    codexWatcher?.setModel(model);
    setModelDisplay(ctx);
  };

  const disposeModelWatchers = (): void => {
    codexWatcher?.dispose();
    codexWatcher = undefined;
  };

  pi.on("session_start", (_event, ctx) => {
    contextGaugeSetTask.reset();
    contextGaugeStatus = new ContextGaugeStatus(ctx.cwd);
    costBudgetStatus = new CostBudgetStatus();
    disposeModelWatchers();

    const model = requireModel(ctx);
    codexWatcher = new CodexConfigWatcher(model, () => {
      modelDisplayDirty = true;
    });
    setCustomFooter(ctx);
    refreshCostBudget(ctx);
  });
  pi.on("model_select", (_event, ctx) => setModel(ctx));
  pi.on("thinking_level_select", (_event, ctx) => setModelDisplay(ctx));
  pi.on("session_tree", (_event, ctx) => {
    contextGaugeSetTask.reset();
    setCustomFooter(ctx);
  });
  pi.on("agent_start", (_event, ctx) => setCustomFooter(ctx));
  pi.on("agent_end", (_event, ctx) => setCustomFooter(ctx));
  pi.on("turn_start", (_event, ctx) => setContextGauge(ctx));
  pi.on("turn_end", (_event, ctx) => {
    setContextGauge(ctx);
    refreshCostBudget(ctx);
    updateWorkspaceDisplayStatuses(ctx);
  });
  pi.on("message_start", (_event, ctx) => setCustomFooter(ctx));
  pi.on("message_update", (_event, ctx) => {
    contextGaugeSetTask.schedule(ctx);
    setModelDisplayIfDirty(ctx);
  });
  pi.on("message_end", (_event, ctx) => setCustomFooter(ctx));
  pi.on("session_compact", (_event, ctx) => setCustomFooter(ctx));
  pi.on("session_shutdown", () => {
    disposeModelWatchers();
    contextGaugeSetTask.reset();
    modelDisplayDirty = false;
  });

  pi.registerCommand("custom-footer-refresh", {
    description: "Refresh pi-powerline-footer-custom status items.",
    handler: async (_args, ctx) => {
      codexWatcher?.refreshFromFile();
      await costBudgetStatus?.update(ctx, true);
      setCustomFooter(ctx);
      ctx.ui.notify("Custom footer statuses refreshed", "info");
    },
  });
}

function requireModel(ctx: ExtensionContext): Model<Api> {
  const model = ctx.model;
  if (!model) throw new Error("pi-powerline-footer-custom requires an active model");
  return model;
}
