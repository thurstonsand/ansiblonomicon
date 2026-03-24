export function stripClaudePrefix(modelName: string): string {
  return modelName.startsWith("Claude ") ? modelName.slice(7) : modelName;
}

export function applyThinkingExponent(label: string, thinkingLevel: unknown): string {
  switch (thinkingLevel) {
    case "high":
      return `${label}²`;
    case "xhigh":
      return `${label}³`;
    default:
      return label;
  }
}
