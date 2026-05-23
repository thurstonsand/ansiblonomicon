export const BASH_TOOL_NAME = "bash";
export const CODEX_EXEC_COMMAND_TOOL_NAME = "exec_command";

export const SHELL_TOOL_NAMES = [BASH_TOOL_NAME, CODEX_EXEC_COMMAND_TOOL_NAME] as const;

export type ShellToolName = (typeof SHELL_TOOL_NAMES)[number];

export type PermissionSubject = {
  kind: "shell-command";
  toolName: ShellToolName;
  command: string;
  detail: string;
};
