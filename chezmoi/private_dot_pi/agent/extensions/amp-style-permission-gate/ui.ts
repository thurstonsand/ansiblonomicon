import type {
  ExtensionCommandContext,
  ExtensionContext,
  Theme,
} from "@mariozechner/pi-coding-agent";
import { matchesKey, visibleWidth } from "@mariozechner/pi-tui";
import type { PermissionRule } from "./rules.js";

function formatPlainSummary(enabled: boolean, rules: PermissionRule[]): string {
  const lines = [`Permission checks: ${enabled ? "enabled" : "disabled"}`, ""];

  for (const [toolName, toolRules] of Map.groupBy(rules, (r) => r.toolName)) {
    lines.push(toolName.toUpperCase());
    for (const rule of toolRules) {
      lines.push(`  ${rule.label}`);
      lines.push(`    ${rule.matcher}`);
    }
    lines.push("");
  }

  lines.push("Usage: /permissions [enable|disable]");
  return lines.join("\n");
}

function formatStyledSummary(theme: Theme, enabled: boolean, rules: PermissionRule[]): string {
  const statusLine = enabled
    ? theme.fg("success", theme.bold("Permission checks enabled"))
    : theme.fg("warning", theme.bold("Permission checks disabled"));
  const lines = [statusLine, ""];

  for (const [toolName, toolRules] of Map.groupBy(rules, (r) => r.toolName)) {
    lines.push(theme.fg("toolTitle", theme.bold(toolName.toUpperCase())));
    for (const rule of toolRules) {
      lines.push(`  ${theme.fg("accent", rule.label)}`);
      lines.push(`    ${theme.fg("dim", `↳ ${rule.matcher}`)}`);
    }
    lines.push("");
  }

  lines.push(theme.fg("muted", "Usage: /permissions [enable|disable]"));
  lines.push(theme.fg("dim", "Enter or Esc to close"));
  return lines.join("\n");
}

function padRight(content: string, width: number): string {
  return content + " ".repeat(Math.max(0, width - visibleWidth(content)));
}

class PermissionsSummaryOverlay {
  readonly width = 84;

  constructor(
    private theme: Theme,
    private enabled: boolean,
    private rules: PermissionRule[],
    private done: () => void,
  ) {}

  handleInput(data: string): void {
    if (matchesKey(data, "escape") || matchesKey(data, "return") || matchesKey(data, "ctrl+c")) {
      this.done();
    }
  }

  render(_width: number): string[] {
    const innerWidth = this.width - 2;
    const border = (text: string) => this.theme.fg("border", text);
    const row = (content = "") => border("│") + padRight(content, innerWidth) + border("│");
    const body = formatStyledSummary(this.theme, this.enabled, this.rules).split("\n");

    return [
      border(`╭${"─".repeat(innerWidth)}╮`),
      row(` ${this.theme.fg("accent", this.theme.bold("Permissions"))}`),
      row(),
      ...body.map((line) => row(` ${line}`)),
      border(`╰${"─".repeat(innerWidth)}╯`),
    ];
  }

  invalidate(): void {}
  dispose(): void {}
}

export function syncPermissionsStatus(ctx: ExtensionContext, enabled: boolean): void {
  if (!ctx.hasUI) return;

  ctx.ui.setStatus(
    "permissions",
    enabled
      ? ctx.ui.theme.fg("accent", "permissions:on")
      : ctx.ui.theme.fg("warning", "permissions:off"),
  );
}

export async function showPermissionsSummary(
  ctx: ExtensionCommandContext,
  enabled: boolean,
  rules: PermissionRule[],
): Promise<void> {
  if (!ctx.hasUI) {
    ctx.ui.notify(formatPlainSummary(enabled, rules), "info");
    return;
  }

  await ctx.ui.custom<void>(
    (_tui, theme, _keybindings, done) =>
      new PermissionsSummaryOverlay(theme, enabled, rules, () => done(undefined)),
    { overlay: true },
  );
}
