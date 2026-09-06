import type { PluginAPI, PluginCommandContext } from "@ampcode/plugin";
import { pendingApprovalNotes } from "./pending-approvals.ts";
import type { PermissionGateState, ThreadID } from "./state.ts";
import type { PermissionStatus } from "./status.ts";

export const TOGGLE_COMMAND_ID = "permission-gate-toggle";

function commandThreadID(
  ctx: PluginCommandContext,
  status: PermissionStatus,
): ThreadID | undefined {
  return ctx.thread?.id ?? status.activeThreadID();
}

export function registerPermissionCommands(
  amp: PluginAPI,
  state: PermissionGateState,
  status: PermissionStatus,
): void {
  amp.registerCommand(
    TOGGLE_COMMAND_ID,
    {
      category: "Permissions",
      title: "Toggle authorization",
      description: "Enable or disable authorization for this thread.",
    },
    async (ctx) => {
      const threadID = commandThreadID(ctx, status);
      if (!threadID) {
        await ctx.ui.notify("No active thread. Permission checks default to enabled.");
        status.updateForThread(undefined);
        return;
      }

      const enabled = state.toggle(threadID);
      if (!enabled) pendingApprovalNotes.discardForThread(threadID);
      status.updateForActiveThread();
      await ctx.ui.notify(
        enabled
          ? "Authorization reinstated for this thread"
          : "Authorization no longer required for this thread... be careful",
      );
    },
  );
}
