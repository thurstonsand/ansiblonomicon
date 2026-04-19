export function stripClaudePrefix(modelName: string): string {
  return modelName.startsWith("Claude ") ? modelName.slice(7) : modelName;
}

export function applyThinkingExponent(label: string, thinkingLevel: unknown): string {
  switch (thinkingLevel) {
    case "off":
    case "instant":
      return `${label}⁻³`;
    case "minimal":
      return `${label}⁻²`;
    case "low":
      return `${label}⁻¹`;
    case "high":
      return `${label}²`;
    case "xhigh":
      return `${label}³`;
    case "max":
      return `${label}⁴`;
    default:
      return label;
  }
}
