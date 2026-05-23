import type { ShellToolName } from "./permission-subject.js";

export type ApprovalNote = {
  ruleLabel: string;
  note: string;
};

export type PermissionPromptInput = {
  ruleLabel: string;
  toolName: ShellToolName;
  detail: string;
};

function formatDecisionLog(label: string, note: string): string {
  return `${label}:\n${note}`;
}

export function formatApprovalNotification({ ruleLabel, note }: ApprovalNote): string {
  return `Operation authorized (${ruleLabel})\n\n${formatDecisionLog("Authorization log", note)}`;
}

export function formatApprovalResultNote({ ruleLabel, note }: ApprovalNote): string {
  return `The user approved this tool use (${ruleLabel}) and provided additional context for how to proceed:\n${note}`;
}

export function formatRejectionNotification(ruleLabel: string, note?: string): string {
  const aborted = `Operation aborted (${ruleLabel})`;
  return note ? `${aborted}\n\n${formatDecisionLog("Abort log", note)}` : aborted;
}

export function formatRejectionResultReason(ruleLabel: string, note?: string): string {
  const blocked = `Blocked by user (${ruleLabel})`;
  if (!note) return blocked;

  return `${blocked}\n\nThe user doesn't want to proceed with this tool use (${ruleLabel}), and it was rejected. To tell you how to proceed, the user said:\n${note}`;
}

export function formatNoUiBlockReason(input: PermissionPromptInput): string {
  return `Blocked ${input.toolName} (${input.ruleLabel}): user confirmation required but no UI available.`;
}

export function formatPermissionPrompt(input: PermissionPromptInput): {
  title: string;
  body: string;
} {
  return {
    title: `! Authorization required: ${input.ruleLabel}`,
    body: `Confirm.\n\n${input.toolName}: ${input.detail}`,
  };
}
