import { basename } from "node:path";
import type { AssistantMessageEvent } from "@earendil-works/pi-ai";
import type {
  BashToolInput,
  EditToolInput,
  FindToolInput,
  GrepToolInput,
  LsToolInput,
  ReadToolInput,
  WriteToolInput,
} from "@earendil-works/pi-coding-agent";

/**
 * The companion status vocabulary. Values are the wire strings the renderer
 * (companion.ts) keys its colors and labels on, so the two must stay in sync.
 */
export const COMPANION_STATUS = {
  starting: "starting",
  thinking: "thinking",
  responding: "responding",
  preparingTool: "preparing_tool",
  reading: "reading",
  editing: "editing",
  running: "running",
  searching: "searching",
  done: "done",
  error: "error",
} as const;

export type CompanionStatus = (typeof COMPANION_STATUS)[keyof typeof COMPANION_STATUS];

export interface CompanionActivity {
  status: CompanionStatus;
  detail?: string;
}

type BuiltInToolArgs =
  | BashToolInput
  | EditToolInput
  | FindToolInput
  | GrepToolInput
  | LsToolInput
  | ReadToolInput
  | WriteToolInput;

export type ToolCallUpdate = Extract<
  AssistantMessageEvent,
  { type: "toolcall_start" | "toolcall_delta" | "toolcall_end" }
>;

export type ThinkingUpdate = Extract<
  AssistantMessageEvent,
  { type: "thinking_start" | "thinking_delta" | "thinking_end" }
>;

export type TextUpdate = Extract<
  AssistantMessageEvent,
  { type: "text_start" | "text_delta" | "text_end" }
>;

export function statusForTool(
  toolName: string,
  args: BuiltInToolArgs | Record<string, unknown>,
): CompanionActivity {
  switch (toolName) {
    case "read":
      return { status: COMPANION_STATUS.reading, detail: basename(stringArg(args, "path")) };
    case "edit":
    case "write":
      return { status: COMPANION_STATUS.editing, detail: basename(stringArg(args, "path")) };
    case "bash":
      return { status: COMPANION_STATUS.running, detail: stringArg(args, "command") };
    case "grep":
    case "find":
    case "ls":
      return {
        status: COMPANION_STATUS.searching,
        detail: stringArg(args, "pattern") || stringArg(args, "path"),
      };
    default:
      return { status: COMPANION_STATUS.running, detail: toolName };
  }
}

export function statusForToolCallUpdate(update: ToolCallUpdate): CompanionActivity {
  if (update.type === "toolcall_end")
    return statusForTool(update.toolCall.name, update.toolCall.arguments);

  const block = update.partial.content[update.contentIndex];
  if (block?.type !== "toolCall" || !block.name) return { status: COMPANION_STATUS.preparingTool };
  return statusForTool(block.name, block.arguments);
}

function stringArg(args: BuiltInToolArgs | Record<string, unknown>, key: string): string {
  const value = (args as Record<string, unknown>)[key];
  return typeof value === "string" ? value : "";
}
