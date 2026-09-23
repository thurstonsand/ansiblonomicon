import type {
  PluginAPI,
  PluginEventContext,
  PluginToolResultContentBlock,
  ToolCallEvent,
  ToolCallResult,
} from "@ampcode/plugin";
import { pendingApprovalNotes } from "./pending-approvals.ts";
import {
  approvalForThreadLabel,
  approvalWithNoteLabel,
  formatApprovalNotification,
  formatEditNotification,
  formatNoUiBlockReason,
  formatPermissionPrompt,
  formatRejectionNotification,
  formatRejectionResultReason,
  formatResultNote,
  formatRuleBlockReason,
  permissionCopy,
  rejectionWithNoteLabel,
} from "./presentation.ts";
import { findMatchingRule, type PermissionRule } from "./rules.ts";
import type { PermissionGateState } from "./state.ts";
import type { PermissionStatus } from "./status.ts";
import { permissionSubjectFromToolCall, type ShellPermissionSubject } from "./subjects.ts";

function prependResultNote(
  resultNote: string,
  output: unknown,
): string | PluginToolResultContentBlock[] {
  if (typeof output === "string") return `${resultNote}\n\n${output}`;

  if (Array.isArray(output)) {
    return [{ type: "text", text: resultNote }, ...output];
  }

  return [{ type: "text", text: resultNote }];
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
    const pendingNote = pendingApprovalNotes.consume(event.thread.id, event.toolUseID);
    if (!pendingNote) return undefined;

    return {
      status: event.status,
      error: event.error,
      output: prependResultNote(formatResultNote(pendingNote), event.output),
    };
  });

  amp.on("tool.call", async (event, ctx) => {
    status.updateForThread(event.thread.id);

    if (!state.isEnabled(event.thread.id)) return { action: "allow" };

    const subject = permissionSubjectFromToolCall(amp, event);
    const match = findMatchingRule(subject);
    if (!match || !state.isRuleEnabled(event.thread.id, match.rule.key)) {
      return { action: "allow" };
    }

    const { rule } = match;
    if ((await ctx.thread.parentThreadID()) !== null) {
      return rule.subagent === "allow"
        ? { action: "allow" }
        : {
            action: "reject-and-continue",
            message: formatRuleBlockReason(rule.name, rule.subagent.blockReason),
          };
    }

    const promptInput = {
      ruleName: rule.name,
      description: rule.description,
      toolName: subject.toolName,
      detail: subject.detail,
    };
    const active = amp.activeThread.current;
    if (active && active.id !== event.thread.id) {
      return {
        action: "reject-and-continue",
        message: formatNoUiBlockReason(promptInput),
      };
    }

    try {
      return await requestPermission(event, ctx, subject, rule, state, status);
    } catch (error) {
      if (error instanceof Error && amp.helpers.isPluginUINotAvailableError(error)) {
        return {
          action: "reject-and-continue",
          message: formatNoUiBlockReason(promptInput),
        };
      }

      throw error;
    }
  });
}

async function requestPermission(
  event: ToolCallEvent,
  ctx: PluginEventContext<"tool.call">,
  subject: ReturnType<typeof permissionSubjectFromToolCall>,
  rule: PermissionRule,
  state: PermissionGateState,
  status: PermissionStatus,
): Promise<ToolCallResult> {
  const prompt = formatPermissionPrompt({
    ruleName: rule.name,
    description: rule.description,
    toolName: subject.toolName,
    detail: subject.detail,
  });
  const approveWithNote = approvalWithNoteLabel(rule);
  const approveForThread = approvalForThreadLabel(rule);
  const rejectWithNote = rejectionWithNoteLabel(rule);
  const options = [
    rule.approveLabel,
    approveWithNote,
    ...(subject.kind === "shell-command" && rule.editLabel ? [rule.editLabel] : []),
    approveForThread,
    rule.rejectLabel,
    rejectWithNote,
  ];

  while (true) {
    const decision = await ctx.ui.select({
      title: prompt.title,
      message: prompt.body,
      initialValue: rule.approveLabel,
      options,
    });

    if (decision === rule.approveLabel) return { action: "allow" };

    if (decision === approveForThread) {
      state.disableRule(event.thread.id, rule.key);
      status.updateForThread(event.thread.id);
      await ctx.ui.notify(`Authorization no longer required (${rule.name})... be careful`);
      return { action: "allow" };
    }

    if (decision === approveWithNote) {
      const note = await ctx.ui.input({
        title: permissionCopy.approvalNoteTitle,
        submitButtonText: permissionCopy.approvalSubmit,
      });
      const trimmed = note?.trim();
      if (trimmed) {
        const approval = { kind: "approval" as const, ruleName: rule.name, note: trimmed };
        await ctx.ui.notify(formatApprovalNotification(approval));
        pendingApprovalNotes.remember(event.thread.id, event.toolUseID, approval);
      }
      return { action: "allow" };
    }

    if (decision === rule.editLabel && subject.kind === "shell-command") {
      const result = await editCommand(event, ctx, subject, rule);
      if (result) return result;
      continue;
    }

    if (decision === rejectWithNote) {
      const note = await ctx.ui.input({
        title: permissionCopy.rejectionNoteTitle,
        submitButtonText: permissionCopy.rejectionSubmit,
      });
      const trimmed = note?.trim();
      await ctx.ui.notify(formatRejectionNotification(rule.name, trimmed));
      return {
        action: "reject-and-continue",
        message: formatRejectionResultReason(rule.name, trimmed),
      };
    }

    await ctx.ui.notify(formatRejectionNotification(rule.name));
    return {
      action: "reject-and-continue",
      message: formatRejectionResultReason(rule.name),
    };
  }
}

async function editCommand(
  event: ToolCallEvent,
  ctx: PluginEventContext<"tool.call">,
  subject: ShellPermissionSubject,
  rule: PermissionRule,
): Promise<ToolCallResult | undefined> {
  const command = await ctx.ui.input({
    title: rule.editLabel ?? "Edit command",
    helpText: "Edit the command that will execute. Cancel to return to the authorization prompt.",
    initialValue: subject.command,
    submitButtonText: rule.editLabel,
  });
  if (command === undefined) return undefined;

  const trimmedCommand = command.trim();
  if (!trimmedCommand) {
    await ctx.ui.notify("An empty command achieves nothing");
    return undefined;
  }

  const note = await ctx.ui.input({
    title: "Directive (optional)",
    helpText: "Add context for the agent, or submit an empty value.",
    submitButtonText: "Continue",
  });
  const trimmedNote = note?.trim();
  pendingApprovalNotes.remember(event.thread.id, event.toolUseID, {
    kind: "edit",
    ruleName: rule.name,
    command: trimmedCommand,
    ...(trimmedNote ? { note: trimmedNote } : {}),
  });
  await ctx.ui.notify(formatEditNotification(rule.name));

  return {
    action: "modify",
    input: { ...event.input, command: trimmedCommand },
  };
}
