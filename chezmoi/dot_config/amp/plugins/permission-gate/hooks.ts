import type { PluginAPI, PluginToolResultContentBlock } from "@ampcode/plugin";
import { pendingApprovalNotes } from "./pending-approvals.ts";
import {
  APPROVE,
  APPROVE_WITH_NOTE,
  formatApprovalNotification,
  formatApprovalResultNote,
  formatNoUiBlockReason,
  formatPermissionPrompt,
  formatRejectionNotification,
  formatRejectionResultReason,
  permissionCopy,
  REJECT,
  REJECT_WITH_NOTE,
} from "./presentation.ts";
import { findMatchingRule } from "./rules.ts";
import type { PermissionGateState } from "./state.ts";
import type { PermissionStatus } from "./status.ts";
import { permissionSubjectFromToolCall } from "./subjects.ts";

function prependApprovalNote(
  approvalNote: string,
  output: unknown,
): string | PluginToolResultContentBlock[] {
  if (typeof output === "string") return `${approvalNote}\n\n${output}`;

  if (Array.isArray(output)) {
    return [{ type: "text", text: approvalNote }, ...output];
  }

  return [{ type: "text", text: approvalNote }];
}

export function registerPermissionHooks(
  amp: PluginAPI,
  state: PermissionGateState,
  status: PermissionStatus,
): void {
  amp.on("session.start", (event) => {
    status.updateForThread(event.thread.id);
  });

  amp.on("agent.end", (event) => {
    pendingApprovalNotes.discardForThread(event.thread.id);
  });

  amp.on("tool.result", (event) => {
    const approval = pendingApprovalNotes.consume(event.thread.id, event.toolUseID);
    if (!approval) return undefined;

    const approvalNote = formatApprovalResultNote(approval);
    const output = event.output;

    return {
      status: event.status,
      error: event.error,
      output: prependApprovalNote(approvalNote, output),
    };
  });

  amp.on("tool.call", async (event, ctx) => {
    status.updateForThread(event.thread.id);

    if (!state.isEnabled(event.thread.id)) return { action: "allow" };

    const subject = permissionSubjectFromToolCall(amp, event);
    if (!subject) return { action: "allow" };

    const match = findMatchingRule(subject);
    if (!match) return { action: "allow" };

    const { rule } = match;
    const active = status.activeThreadID();
    if (active && active !== event.thread.id) {
      return {
        action: "reject-and-continue",
        message: formatNoUiBlockReason({
          ruleLabel: rule.label,
          toolName: subject.toolName,
          detail: subject.detail,
        }),
      };
    }

    const prompt = formatPermissionPrompt({
      ruleLabel: rule.label,
      toolName: subject.toolName,
      detail: subject.detail,
    });

    try {
      const decision = await ctx.ui.select({
        title: prompt.title,
        message: prompt.body,
        initialValue: APPROVE,
        options: [APPROVE, APPROVE_WITH_NOTE, REJECT, REJECT_WITH_NOTE],
      });

      switch (decision) {
        case APPROVE:
          return { action: "allow" };
        case APPROVE_WITH_NOTE: {
          const note = await ctx.ui.input({
            title: permissionCopy.approvalNoteTitle,
            submitButtonText: permissionCopy.approvalSubmit,
          });

          const trimmed = note?.trim();
          if (trimmed) {
            await ctx.ui.notify(
              formatApprovalNotification({
                ruleLabel: rule.label,
                note: trimmed,
              }),
            );
            pendingApprovalNotes.remember(event.thread.id, event.toolUseID, {
              ruleLabel: rule.label,
              note: trimmed,
            });
          }
          return { action: "allow" };
        }
        case REJECT_WITH_NOTE: {
          const note = await ctx.ui.input({
            title: permissionCopy.rejectionNoteTitle,
            submitButtonText: permissionCopy.rejectionSubmit,
          });

          const trimmed = note?.trim();
          await ctx.ui.notify(formatRejectionNotification(rule.label, trimmed));
          return {
            action: "reject-and-continue",
            message: formatRejectionResultReason(rule.label, trimmed),
          };
        }
        default:
          await ctx.ui.notify(formatRejectionNotification(rule.label));
          return {
            action: "reject-and-continue",
            message: formatRejectionResultReason(rule.label),
          };
      }
    } catch (error) {
      if (error instanceof Error && amp.helpers.isPluginUINotAvailableError(error)) {
        return {
          action: "reject-and-continue",
          message: formatNoUiBlockReason({
            ruleLabel: rule.label,
            toolName: subject.toolName,
            detail: subject.detail,
          }),
        };
      }

      throw error;
    }
  });
}
