import type { ExtensionCommandContext, Theme } from "@earendil-works/pi-coding-agent";
import type { Focusable, TUI, TuiMouseEvent, TuiMouseEventResult } from "@earendil-works/pi-tui";
import { matchesKey, truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";
import { cycleSummary, cycleVerbosity, formatCodexSettings } from "./command.js";
import { shouldApplyCodexSettings } from "./request.js";
import { type CodexSettings, loadCodexSettingsState, saveCodexSettings } from "./settings.js";

export async function showCodexPanel(ctx: ExtensionCommandContext): Promise<void> {
  await ctx.ui.custom<void>(
    (tui, theme, _keybindings, done) => new CodexPanel(tui, theme, ctx, done),
    {
      overlay: true,
      overlayOptions: {
        anchor: "center",
        width: 72,
        margin: 1,
      },
    },
  );
}

type PanelAction = "f" | "v" | "s" | "q";

interface ActionHit {
  row: number;
  start: number;
  end: number;
  action: PanelAction;
}

class CodexPanel implements Focusable {
  focused = false;
  private settings: CodexSettings;
  private actionHits: ActionHit[] = [];
  private pressedAction: PanelAction | undefined;

  constructor(
    private readonly tui: TUI,
    private readonly theme: Theme,
    private readonly ctx: ExtensionCommandContext,
    private readonly done: (result: undefined) => void,
  ) {
    this.settings = loadCodexSettingsState().settings;
  }

  invalidate(): void {}

  handleInput(data: string): void {
    if (matchesKey(data, "escape") || data === "q" || data === "Q") {
      this.done(undefined);
      return;
    }

    if (data === "f" || data === "F") {
      this.update({ ...this.settings, fast: !this.settings.fast });
      return;
    }

    if (data === "v" || data === "V") {
      this.update(cycleVerbosity(this.settings));
      return;
    }

    if (data === "s" || data === "S") {
      this.update(cycleSummary(this.settings));
    }
  }

  handleMouse(event: TuiMouseEvent): TuiMouseEventResult | undefined {
    if (event.type === "press") {
      const wasPressed = this.pressedAction !== undefined;
      this.pressedAction =
        event.button === "left"
          ? this.actionHits.find(
              (hit) => event.y === hit.row && event.x >= hit.start && event.x < hit.end,
            )?.action
          : undefined;
      if (this.pressedAction) return { handled: true };
      if (wasPressed) this.tui.requestRender();
      return undefined;
    }

    if (event.button !== "left") return undefined;
    if (event.type === "drag" && this.pressedAction) {
      this.pressedAction = undefined;
      return { handled: true };
    }
    if (event.type === "click" && this.pressedAction) {
      const action = this.pressedAction;
      this.pressedAction = undefined;
      this.handleInput(action);
      return { handled: true };
    }
    return undefined;
  }

  render(width: number): string[] {
    this.actionHits = [];
    const innerWidth = Math.max(1, width - 2);
    const lines: string[] = [this.theme.fg("border", `╭${"─".repeat(innerWidth)}╮`)];

    lines.push(this.renderHeaderRow(innerWidth));
    lines.push(this.renderRow(innerWidth, ""));
    lines.push(
      this.renderRow(innerWidth, ` ${this.theme.fg("dim", "Provider:")} ${this.providerLabel()}`),
    );
    lines.push(this.renderRow(innerWidth, ""));
    lines.push(
      this.renderActionRow(
        innerWidth,
        lines.length,
        "f",
        "Fast priority",
        this.settings.fast ? "on" : "off",
      ),
    );
    lines.push(
      this.renderActionRow(innerWidth, lines.length, "v", "Verbosity", this.settings.verbosity),
    );
    lines.push(
      this.renderActionRow(
        innerWidth,
        lines.length,
        "s",
        "Reasoning summary",
        this.settings.reasoningSummary,
      ),
    );
    lines.push(this.renderRow(innerWidth, ""));
    lines.push(
      this.renderControlRow(
        innerWidth,
        lines.length,
        "q",
        `${this.theme.fg("dim", "q/Esc")} close`,
      ),
    );

    lines.push(this.theme.fg("border", `╰${"─".repeat(innerWidth)}╯`));
    return lines.map((line) => truncateToWidth(line, width));
  }

  private update(settings: CodexSettings): void {
    this.settings = settings;
    saveCodexSettings(settings);
    this.ctx.ui.notify(formatCodexSettings(settings), "info");
    this.tui.requestRender();
  }

  private renderHeaderRow(innerWidth: number): string {
    return this.renderRow(innerWidth, ` ${this.theme.bold(this.theme.fg("accent", "Codex"))}`);
  }

  private renderActionRow(
    innerWidth: number,
    row: number,
    key: PanelAction,
    label: string,
    value: string,
  ): string {
    const keyText = this.theme.bold(key);
    const valueText = this.theme.fg("accent", value);
    return this.renderControlRow(innerWidth, row, key, `${keyText} ${label}: ${valueText}`);
  }

  private renderControlRow(
    innerWidth: number,
    row: number,
    action: PanelAction,
    text: string,
  ): string {
    const textWidth = visibleWidth(text);
    if (textWidth + 1 <= innerWidth) {
      this.actionHits.push({ row, start: 2, end: 2 + textWidth, action });
    }
    const content = this.pressedAction === action ? this.theme.bg("selectedBg", text) : text;
    return this.renderRow(innerWidth, ` ${content}`);
  }

  private renderRow(innerWidth: number, content: string): string {
    content = truncateToWidth(content, innerWidth);
    const pad = Math.max(0, innerWidth - visibleWidth(content));
    return `${this.theme.fg("border", "│")}${content}${" ".repeat(pad)}${this.theme.fg("border", "│")}`;
  }

  private providerLabel(): string {
    const model = this.ctx.model;
    if (!model) return "no model";

    const label = `${model.provider}/${model.id}`;
    return shouldApplyCodexSettings(model)
      ? this.theme.fg("accent", label)
      : this.theme.fg("dim", label);
  }
}
