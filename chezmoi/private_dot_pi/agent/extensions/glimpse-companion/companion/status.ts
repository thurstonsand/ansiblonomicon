import { basename } from "node:path";

/**
 * The companion status vocabulary. Values are the wire strings the renderer
 * (companion.ts) keys its colors and labels on, so the two must stay in sync.
 */
export const COMPANION_STATUS = {
  starting: "starting",
  thinking: "thinking",
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

export function statusForTool(
  toolName: string,
  args: Record<string, string | undefined>,
): CompanionActivity {
  switch (toolName) {
    case "read":
      return { status: COMPANION_STATUS.reading, detail: basename(args.path ?? "") };
    case "edit":
    case "write":
      return { status: COMPANION_STATUS.editing, detail: basename(args.path ?? "") };
    case "bash":
      return { status: COMPANION_STATUS.running, detail: args.command ?? "" };
    case "grep":
    case "find":
    case "ls":
      return { status: COMPANION_STATUS.searching, detail: args.pattern ?? args.path ?? "" };
    default:
      return { status: COMPANION_STATUS.running, detail: toolName };
  }
}
