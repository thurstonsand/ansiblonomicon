import type { ThemeColor } from "@earendil-works/pi-coding-agent";

const GAUGE_WIDTH = 21;
const WARN_AT = 50;
const ERROR_AT = 80;

export function renderGauge(percent: number, overSoftMax = false): string {
  const label = Math.max(0, Math.round(percent)).toString().padStart(2, "0");
  const text = `${label}${overSoftMax ? "!" : "%"}`;
  const clamped = Math.max(0, Math.min(percent, 100));
  const visibleBarWidth = Math.max(0, GAUGE_WIDTH - text.length);
  const filled = Math.round((clamped / 100) * visibleBarWidth);
  const empty = visibleBarWidth - filled;

  return `[${"━".repeat(filled)}${text}${"─".repeat(empty)}]`;
}

export function colorForPercent(percent: number, overSoftMax = false): ThemeColor {
  if (overSoftMax || percent >= ERROR_AT) return "error";
  if (percent >= WARN_AT) return "warning";
  return "muted";
}
