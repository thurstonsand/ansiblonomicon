import {
  type ExtensionAPI,
  type ExtensionContext,
  isToolCallEventType,
} from "@earendil-works/pi-coding-agent";
import { BASH_TOOL_NAME, findMatchingRule, PERMISSION_RULES } from "./rules.js";
import { persistPermissionGateState, restorePermissionGateState } from "./state.js";
import { showPermissionGate, showPermissionsSummary, syncPermissionsStatus } from "./ui.js";

export default function ampStylePermissionGate(pi: ExtensionAPI) {
  let checksEnabled = true;
  const pendingApprovedNotes = new Map<string, { ruleLabel: string; note: string }>();

  function formatApprovalNote(ruleLabel: string, note: string): string {
    return `---\nOperation authorized (${ruleLabel})\n\nUser note:\n${note}`;
  }

  function formatRejectionNote(note: string): string {
    return `Log:\n${note}`;
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
            checksEnabled
              ? "Authorization reinstated for this session branch"
              : "Authorization no longer required for this session branch... be careful",
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
  pi.on("session_before_fork", async (_event, ctx) => restoreState(ctx));
  pi.on("turn_end", () => pendingApprovedNotes.clear());
  pi.on("tool_result", async (event) => {
    const approval = pendingApprovedNotes.get(event.toolCallId);
    if (!approval) return undefined;

    pendingApprovedNotes.delete(event.toolCallId);
    return {
      content: [
        ...event.content,
        { type: "text" as const, text: formatApprovalNote(approval.ruleLabel, approval.note) },
      ],
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
      `⚠ Authorization required: ${rule.label}`,
      `Confirm.\n\n${rule.toolName}: ${promptDetail}`,
    );

    switch (decision.kind) {
      case "allow":
        return undefined;
      case "allow_with_note":
        pendingApprovedNotes.set(event.toolCallId, { ruleLabel: rule.label, note: decision.note });
        return undefined;
      case "reject": {
        const reason = decision.note
          ? `Operation aborted (${rule.label})\n\n${formatRejectionNote(decision.note)}`
          : `Operation aborted (${rule.label})`;
        if (decision.abort) {
          // Defer so the block result propagates before the turn is torn down.
          setTimeout(() => ctx.abort(), 0);
        }
        return { block: true, reason };
      }
    }
  });
}
