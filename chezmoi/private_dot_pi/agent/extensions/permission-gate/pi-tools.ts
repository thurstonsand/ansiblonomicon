import {
  type BashToolCallEvent,
  isToolCallEventType,
  type ToolCallEvent,
} from "@earendil-works/pi-coding-agent";
import {
  BASH_TOOL_NAME,
  CODEX_EXEC_COMMAND_TOOL_NAME,
  type PermissionSubject,
  WEB_SEARCH_SUBJECT_TOOL,
  WEB_SEARCH_TOOL_PATTERN,
} from "./permission-subject.js";

type CodexExecCommandInput = { cmd?: unknown };

const MCP_GATEWAY_TOOL_NAME = "mcp";

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

  if (isWebSearchToolCall(event)) {
    return webSearchSubject(event);
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

function webSearchSubject(event: ToolCallEvent): PermissionSubject {
  return {
    kind: "tool-invocation",
    toolName: WEB_SEARCH_SUBJECT_TOOL,
    detail: webSearchQuery(event) ?? webSearchTarget(event),
  };
}

// Recognize a web search whether it arrives as a direct adapter tool
// (web-search_web_search) or through the mcp() gateway (tool: "web_search").
function isWebSearchToolCall(event: ToolCallEvent): boolean {
  return WEB_SEARCH_TOOL_PATTERN.test(webSearchTarget(event));
}

function webSearchTarget(event: ToolCallEvent): string {
  const input = event.input as Record<string, unknown>;
  if (event.toolName === MCP_GATEWAY_TOOL_NAME && typeof input.tool === "string") {
    return input.tool;
  }
  return event.toolName;
}

function webSearchQuery(event: ToolCallEvent): string | undefined {
  const input = event.input as Record<string, unknown>;
  if (event.toolName === MCP_GATEWAY_TOOL_NAME) {
    return typeof input.args === "string" ? parseQuery(input.args) : undefined;
  }
  return typeof input.query === "string" ? input.query : undefined;
}

function parseQuery(args: string): string | undefined {
  try {
    const parsed = JSON.parse(args) as { query?: unknown };
    return typeof parsed.query === "string" ? parsed.query : undefined;
  } catch {
    return undefined;
  }
}
