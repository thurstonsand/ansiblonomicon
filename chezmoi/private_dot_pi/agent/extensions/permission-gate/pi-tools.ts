import {
  type BashToolCallEvent,
  isToolCallEventType,
  type ToolCallEvent,
} from "@earendil-works/pi-coding-agent";
import {
  BASH_TOOL_NAME,
  CODEX_EXEC_COMMAND_TOOL_NAME,
  type PermissionSubject,
} from "./permission-subject.js";

type CodexExecCommandInput = { cmd?: unknown };

export function permissionSubjectFromToolCall(event: ToolCallEvent): PermissionSubject | undefined {
  if (isToolCallEventType(BASH_TOOL_NAME, event)) {
    return shellCommandSubject(BASH_TOOL_NAME, event.input.command);
  }

  if (
    isToolCallEventType<typeof CODEX_EXEC_COMMAND_TOOL_NAME, CodexExecCommandInput>(
      CODEX_EXEC_COMMAND_TOOL_NAME,
      event,
    )
  ) {
    return shellCommandSubject(CODEX_EXEC_COMMAND_TOOL_NAME, String(event.input.cmd ?? ""));
  }

  return undefined;
}

function shellCommandSubject(
  toolName: BashToolCallEvent["toolName"] | typeof CODEX_EXEC_COMMAND_TOOL_NAME,
  command: string,
): PermissionSubject {
  return {
    kind: "shell-command",
    toolName,
    command,
    detail: command,
  };
}
