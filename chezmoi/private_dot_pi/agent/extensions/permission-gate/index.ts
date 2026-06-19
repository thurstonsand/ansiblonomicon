import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { PendingApprovalNotes } from "./pending-approvals.js";
import { permissionSubjectFromToolCall } from "./pi-tools.js";
import {
  formatApprovalNotification,
  formatApprovalResultNote,
  formatNoUiBlockReason,
  formatPermissionPrompt,
  formatRejectionNotification,
  formatRejectionResultReason,
  type PermissionPromptInput,
} from "./presentation.js";
import { findMatchingRule, PERMISSION_RULES } from "./rules.js";
import { persistPermissionGateState, restorePermissionGateState } from "./state.js";
import { showPermissionGate, showPermissionsSummary, syncPermissionsStatus } from "./ui.js";

export default function permissionGate(pi: ExtensionAPI) {
  let checksEnabled = true;
  const pendingApprovalNotes = new PendingApprovalNotes();

  function restoreState(ctx: ExtensionContext): void {
    pendingApprovalNotes.discardOutstandingNotes();
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
  pi.on("turn_end", () => pendingApprovalNotes.discardOutstandingNotes());
  pi.on("tool_result", async (event) => {
    const approval = pendingApprovalNotes.consumeForToolResult(event.toolCallId);
    if (!approval) return undefined;

    return {
      content: [
        {
          type: "text" as const,
          text: formatApprovalResultNote(approval),
        },
        ...event.content,
      ],
    };
  });

  pi.on("tool_call", async (event, ctx) => {
    if (!checksEnabled) return undefined;

    const subject = permissionSubjectFromToolCall(event);
    if (!subject) return undefined;

    const match = findMatchingRule(subject);
    if (!match) return undefined;

    const { rule } = match;
    const promptInput: PermissionPromptInput = {
      ruleLabel: rule.label,
      toolName: subject.toolName,
      detail: subject.detail,
    };

    if (!ctx.hasUI) {
      return {
        block: true,
        reason: formatNoUiBlockReason(promptInput),
      };
    }

    const prompt = formatPermissionPrompt(promptInput);
    pi.events.emit("glimpseui:attention:request", {
      attentionId: event.toolCallId,
      label: rule.label,
    });
    let decision: Awaited<ReturnType<typeof showPermissionGate>>;
    try {
      decision = await showPermissionGate(ctx, prompt.title, prompt.body);
    } finally {
      pi.events.emit("glimpseui:attention:resolve", { attentionId: event.toolCallId });
    }

    switch (decision.kind) {
      case "allow":
        return undefined;
      case "allow_with_note":
        ctx.ui.notify(
          formatApprovalNotification({ ruleLabel: rule.label, note: decision.note }),
          "warning",
        );
        pendingApprovalNotes.rememberForToolResult(event.toolCallId, {
          ruleLabel: rule.label,
          note: decision.note,
        });
        return undefined;
      case "reject": {
        const reason = formatRejectionResultReason(rule.label, decision.note);
        ctx.ui.notify(formatRejectionNotification(rule.label, decision.note), "warning");
        if (decision.abort) {
          // Defer so the block result propagates before the turn is torn down.
          setTimeout(() => ctx.abort(), 0);
        }
        return { block: true, reason };
      }
    }
  });
}
