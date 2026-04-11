import {
  type ExtensionAPI,
  type ExtensionContext,
  isToolCallEventType,
} from "@mariozechner/pi-coding-agent";
import { BASH_TOOL_NAME, findMatchingRule, PERMISSION_RULES } from "./rules.js";
import { persistPermissionGateState, restorePermissionGateState } from "./state.js";
import { showPermissionsSummary, syncPermissionsStatus } from "./ui.js";

export default function ampStylePermissionGate(pi: ExtensionAPI) {
  let checksEnabled = true;

  function restoreState(ctx: ExtensionContext): void {
    checksEnabled = restorePermissionGateState(ctx);
    syncPermissionsStatus(ctx, checksEnabled);
  }

  pi.registerCommand("permissions", {
    description: "List or toggle permission checks",
    getArgumentCompletions(prefix) {
      const actions = ["enable", "disable"];
      const filtered = actions.filter((a) => a.startsWith(prefix));
      return filtered.length > 0 ? filtered.map((a) => ({ value: a, label: a })) : null;
    },
    async handler(args, ctx) {
      const action = args.trim();
      switch (action) {
        case "":
          await showPermissionsSummary(ctx, checksEnabled, PERMISSION_RULES);
          break;
        case "enable":
        case "disable":
          checksEnabled = action === "enable";
          persistPermissionGateState(pi, checksEnabled);
          syncPermissionsStatus(ctx, checksEnabled);
          ctx.ui.notify(
            `Permission checks ${checksEnabled ? "enabled" : "disabled"} for this session branch`,
            checksEnabled ? "info" : "warning",
          );
          break;
        default:
          ctx.ui.notify("Usage: /permissions [enable|disable]", "warning");
      }
    },
  });

  pi.on("session_start", async (_event, ctx) => restoreState(ctx));
  pi.on("session_tree", async (_event, ctx) => restoreState(ctx));
  pi.on("session_fork", async (_event, ctx) => restoreState(ctx));

  pi.on("tool_call", async (event, ctx) => {
    if (!checksEnabled) return undefined;

    const rule = findMatchingRule(event);
    if (!rule) return undefined;

    const promptDetail = isToolCallEventType(BASH_TOOL_NAME, event)
      ? String(event.input.command ?? "")
      : `${rule.toolName} tool call`;

    if (!ctx.hasUI) {
      return {
        block: true,
        reason: `Blocked ${rule.toolName} (${rule.label}): user confirmation required but no UI available.`,
      };
    }

    const allowed = await ctx.ui.confirm(
      `⚠ ${rule.label}`,
      `Confirm.\n\n${rule.toolName}: ${promptDetail}`,
    );

    return allowed ? undefined : { block: true, reason: `Blocked by user (${rule.label})` };
  });
}
