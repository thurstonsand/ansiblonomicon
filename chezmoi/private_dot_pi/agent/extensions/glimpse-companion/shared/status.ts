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
