export const BASH_TOOL_NAME = "bash";
export const CODEX_EXEC_COMMAND_TOOL_NAME = "exec_command";

export const SHELL_TOOL_NAMES = [BASH_TOOL_NAME, CODEX_EXEC_COMMAND_TOOL_NAME] as const;

export type ShellToolName = (typeof SHELL_TOOL_NAMES)[number];

// Canonical name for any web-search tool.
export const WEB_SEARCH_SUBJECT_TOOL = "web_search";
export const WEB_SEARCH_TOOL_PATTERN = /web[_-]?search$/i;

export type ShellCommandSubject = {
  kind: "shell-command";
  toolName: ShellToolName;
  command: string;
  detail: string;
};

export type ToolInvocationSubject = {
  kind: "tool-invocation";
  toolName: string;
  detail: string;
};

export type PermissionSubject = ShellCommandSubject | ToolInvocationSubject;
