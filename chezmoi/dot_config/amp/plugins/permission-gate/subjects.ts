import type { PluginAPI, ToolCall } from "@ampcode/plugin";

export type ShellPermissionSubject = {
  kind: "shell-command";
  toolName: string;
  command: string;
  detail: string;
};

export type ToolPermissionSubject = {
  kind: "tool-call";
  toolName: string;
  input: Record<string, unknown>;
  detail: string;
};

export type PermissionSubject = ShellPermissionSubject | ToolPermissionSubject;

export function permissionSubjectFromToolCall(amp: PluginAPI, event: ToolCall): PermissionSubject {
  const shellCommand = amp.helpers.shellCommandFromToolCall(event);
  if (shellCommand) {
    return {
      kind: "shell-command",
      toolName: event.tool,
      command: shellCommand.command,
      detail: shellCommand.dir
        ? `${shellCommand.command}\n\nWorking directory:\n${shellCommand.dir}`
        : shellCommand.command,
    };
  }

  return {
    kind: "tool-call",
    toolName: event.tool,
    input: event.input,
    detail: JSON.stringify(event.input, null, 2),
  };
}
