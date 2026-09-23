import { basename } from "node:path";
import type { AssistantMessageEvent } from "@earendil-works/pi-ai";
import { COMPANION_STATUS, type CompanionStatusLabel } from "../shared/status.js";

export interface CompanionActivity {
  status: CompanionStatusLabel;
  detail?: string;
}

/**
 * Declarative recipe for a tool's companion detail text: which argument value to
 * surface (first non-empty wins when several are listed), and an optional
 * transform applied to the chosen value.
 */
export interface ToolDetail {
  from?: string | string[];
  transform?: "basename";
}

/** Per-tool companion activity: its status and how to derive its detail. */
export interface ToolConfig {
  status?: CompanionStatusLabel;
  detail?: ToolDetail;
}

export type ToolConfigOverrides = Record<string, ToolConfig>;

const DEFAULT_TOOL_CONFIGS: ToolConfigOverrides = {
  read: {
    status: COMPANION_STATUS.reading,
    detail: { from: "path", transform: "basename" },
  },
  edit: {
    status: COMPANION_STATUS.editing,
    detail: { from: "path", transform: "basename" },
  },
  write: {
    status: COMPANION_STATUS.editing,
    detail: { from: "path", transform: "basename" },
  },
  bash: { status: COMPANION_STATUS.running, detail: { from: "command" } },
  grep: {
    status: COMPANION_STATUS.searching,
    detail: { from: ["pattern", "path"] },
  },
  find: {
    status: COMPANION_STATUS.searching,
    detail: { from: ["pattern", "path"] },
  },
  ls: {
    status: COMPANION_STATUS.searching,
    detail: { from: ["pattern", "path"] },
  },
};

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
  args: Record<string, unknown>,
  overrides: ToolConfigOverrides = {},
): CompanionActivity {
  const config = overrides[toolName] ?? DEFAULT_TOOL_CONFIGS[toolName];
  if (!config) return { status: COMPANION_STATUS.running, detail: toolName };

  return {
    status: config.status ?? COMPANION_STATUS.running,
    detail: resolveDetail(config.detail, args),
  };
}

export function statusForToolCallUpdate(
  update: ToolCallUpdate,
  overrides: ToolConfigOverrides = {},
): CompanionActivity {
  if (update.type === "toolcall_end")
    return statusForTool(update.toolCall.name, update.toolCall.arguments, overrides);

  const block = update.partial.content[update.contentIndex];
  if (block?.type !== "toolCall" || !block.name) return { status: COMPANION_STATUS.preparingTool };
  return statusForTool(block.name, block.arguments, overrides);
}

function resolveDetail(detail: ToolDetail | undefined, args: Record<string, unknown>): string {
  const keys = detail?.from === undefined ? [] : [detail.from].flat();
  for (const key of keys) {
    const value = stringArg(args, key);
    if (value) return detail?.transform === "basename" ? basename(value) : value;
  }
  return "";
}

function stringArg(args: Record<string, unknown>, key: string): string {
  const value = args[key];
  return typeof value === "string" ? value : "";
}
