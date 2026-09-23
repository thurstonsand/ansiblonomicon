export const COMPANION_STATUS = {
  starting: "starting",
  thinking: "thinking",
  responding: "responding",
  preparingTool: "preparing_tool",
  reading: "reading",
  editing: "editing",
  running: "running",
  searching: "searching",
  compacting: "compacting",
  done: "done",
  error: "error",
} as const;

export type CompanionStatus = (typeof COMPANION_STATUS)[keyof typeof COMPANION_STATUS];

/**
 * A status preset or an arbitrary label. Presets render with their themed dot
 * color and canonical label; any other string renders verbatim with the
 * `running` color as a fallback.
 */
export type CompanionStatusLabel = CompanionStatus | (string & {});
