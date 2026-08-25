import type { PermissionRule } from "./rules.ts";

export type ApprovalNote = {
  kind: "approval";
  ruleName: string;
  note: string;
};

export type EditNote = {
  kind: "edit";
  ruleName: string;
  command: string;
  note?: string;
};

export type PendingResultNote = ApprovalNote | EditNote;

export type PermissionPromptInput = {
  ruleName: string;
  description: string;
  toolName: string;
  detail: string;
};

export const permissionCopy = {
  approvalNoteTitle: "Directive",
  approvalSubmit: "Authorize",
  rejectionNoteTitle: "Directive",
  rejectionSubmit: "Abort",
};

function formatDecisionLog(label: string, note: string): string {
  return `${label}:\n${note}`;
}

export function approvalWithNoteLabel(rule: PermissionRule): string {
  return `${rule.approveLabel} with directive`;
}

export function approvalForThreadLabel(rule: PermissionRule): string {
  return `${rule.approveLabel} for thread`;
}

export function rejectionWithNoteLabel(rule: PermissionRule): string {
  return `${rule.rejectLabel} with directive`;
}

export function formatApprovalNotification({ ruleName, note }: ApprovalNote): string {
  return `Operation authorized (${ruleName})\n\n${formatDecisionLog("Authorization log", note)}`;
}

export function formatEditNotification(ruleName: string): string {
  return `Command edited (${ruleName})`;
}

export function formatResultNote(note: PendingResultNote): string {
  if (note.kind === "approval") {
    return `The user approved this tool use (${note.ruleName}) and provided additional context for how to proceed:\n${note.note}`;
  }

  const edited = `The user edited this command before execution (${note.ruleName}). The command that actually ran:\n${note.command}`;
  return note.note ? `${edited}\n\nThe user also provided context:\n${note.note}` : edited;
}

export function formatRejectionNotification(ruleName: string, note?: string): string {
  const aborted = `Operation aborted (${ruleName})`;
  return note ? `${aborted}\n\n${formatDecisionLog("Abort log", note)}` : aborted;
}

export function formatRejectionResultReason(ruleName: string, note?: string): string {
  const blocked = `Blocked by user (${ruleName})`;
  if (!note) return blocked;

  return `${blocked}\n\nThe user doesn't want to proceed with this tool use, and said:\n${note}`;
}

export function formatRuleBlockReason(ruleName: string, reason: string): string {
  return `Blocked by permission rule ${ruleName}\n\n${reason}`;
}

export function formatNoUiBlockReason(input: PermissionPromptInput): string {
  return `Blocked ${input.toolName} (${input.ruleName}): user confirmation required but no UI available.`;
}

export function formatPermissionPrompt(input: PermissionPromptInput): {
  title: string;
  body: string;
} {
  return {
    title: `! Authorization required: ${input.ruleName}`,
    body: `${input.description}\n\n${input.toolName}: ${input.detail}`,
  };
}
