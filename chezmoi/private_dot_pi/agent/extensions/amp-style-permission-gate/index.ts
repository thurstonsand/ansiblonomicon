import {
  type ExtensionAPI,
  type ExtensionContext,
  isToolCallEventType,
} from "@mariozechner/pi-coding-agent";
import { BASH_TOOL_NAME, findMatchingRule, PERMISSION_RULES } from "./rules.js";
import { persistPermissionGateState, restorePermissionGateState } from "./state.js";
import {
  showPermissionGate,
  showPermissionsSummary,
  syncPermissionsStatus,
} from "./ui.js";

export default function ampStylePermissionGate(pi: ExtensionAPI) {
  let checksEnabled = true;
  const pendingApprovedNotes = new Map<string, string>();

  function formatApprovalNote(note: string): string {
    return `User approved this tool use. Alongside their approval, the user said:\n${note}\n---`;
  }

  function formatRejectionNote(note: string): string {
    return `The user doesn't want to proceed with this tool use, and it was rejected. To tell you how to proceed, the user said:\n${note}`;
  }

  function restoreState(ctx: ExtensionContext): void {
    pendingApprovedNotes.clear();
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
  pi.on("turn_end", () => pendingApprovedNotes.clear());
  pi.on("tool_result", async (event) => {
    const note = pendingApprovedNotes.get(event.toolCallId);
    if (!note) return undefined;

    pendingApprovedNotes.delete(event.toolCallId);
    return {
      content: [{ type: "text" as const, text: formatApprovalNote(note) }, ...event.content],
    };
  });

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

    const decision = await showPermissionGate(
      ctx,
      `⚠ ${rule.label}`,
      `Confirm.\n\n${rule.toolName}: ${promptDetail}`,
    );

    switch (decision.kind) {
      case "allow":
        return undefined;
      case "allow_with_note":
        pendingApprovedNotes.set(event.toolCallId, decision.note);
        return undefined;
      case "reject": {
        const reason = decision.note
          ? `Blocked by user (${rule.label})\n\n${formatRejectionNote(decision.note)}`
          : `Blocked by user (${rule.label})`;
        if (decision.abort) {
          // Defer so the block result propagates before the turn is torn down.
          setTimeout(() => ctx.abort(), 0);
        }
        return { block: true, reason };
      }
    }
  });
}
