import type { ExtensionContext } from "@earendil-works/pi-coding-agent";

const ENABLE_FOCUS_REPORTING = "\x1b[?1004h";
const DISABLE_FOCUS_REPORTING = "\x1b[?1004l";
const FOCUS_IN = "\x1b[I";
const FOCUS_OUT = "\x1b[O";

export interface TerminalInput {
  data: string;
  focused: boolean;
  includesFocusReport: boolean;
}

export function parseTerminalInput(data: string): TerminalInput {
  let focused = true;
  let includesFocusReport = false;
  let remaining = "";
  let offset = 0;

  while (offset < data.length) {
    const focusInIndex = data.indexOf(FOCUS_IN, offset);
    const focusOutIndex = data.indexOf(FOCUS_OUT, offset);
    const reportIndex =
      focusInIndex === -1
        ? focusOutIndex
        : focusOutIndex === -1
          ? focusInIndex
          : Math.min(focusInIndex, focusOutIndex);

    if (reportIndex === -1) {
      const trailingData = data.slice(offset);
      if (trailingData) {
        remaining += trailingData;
        focused = true;
      }
      break;
    }

    if (reportIndex > offset) {
      remaining += data.slice(offset, reportIndex);
      focused = true;
    }
    focused = reportIndex === focusInIndex;
    includesFocusReport = true;
    offset = reportIndex + FOCUS_IN.length;
  }

  return { data: remaining, focused, includesFocusReport };
}

export interface FocusTerminal {
  readonly inputIsTTY: boolean;
  readonly outputIsTTY: boolean;
  write(data: string): void;
  on(event: "pause" | "resume", listener: () => void): void;
  off(event: "pause" | "resume", listener: () => void): void;
}

const processTerminal: FocusTerminal = {
  get inputIsTTY() {
    return process.stdin.isTTY;
  },
  get outputIsTTY() {
    return process.stdout.isTTY;
  },
  write(data) {
    process.stdout.write(data);
  },
  on(event, listener) {
    process.stdin.on(event, listener);
  },
  off(event, listener) {
    process.stdin.off(event, listener);
  },
};

export class TerminalFocusTracker {
  // DEC focus reporting has no current-state query. Assume focused so a missing
  // initial report preserves the normal Done expiry instead of pinning forever.
  private focused = true;
  private started = false;
  private reporting = false;
  private unsubscribe: (() => void) | undefined;
  private onFocusChange: ((focused: boolean) => void) | undefined;

  constructor(private readonly terminal: FocusTerminal = processTerminal) {}

  get isFocused(): boolean {
    return this.focused;
  }

  start(ctx: ExtensionContext, onFocusChange: (focused: boolean) => void): void {
    if (
      this.started ||
      ctx.mode !== "tui" ||
      !this.terminal.inputIsTTY ||
      !this.terminal.outputIsTTY
    )
      return;

    this.started = true;
    this.focused = true;
    this.onFocusChange = onFocusChange;
    this.unsubscribe = ctx.ui.onTerminalInput((data) => {
      const input = parseTerminalInput(data);
      if (input.focused !== this.focused) {
        this.focused = input.focused;
        this.onFocusChange?.(input.focused);
      }
      if (!input.includesFocusReport) return;
      if (!input.data) return { consume: true };
      return { data: input.data };
    });
    this.terminal.on("pause", this.disableReporting);
    this.terminal.on("resume", this.enableReporting);
    this.enableReporting();
  }

  stop(): void {
    if (!this.started) return;

    this.disableReporting();
    this.unsubscribe?.();
    this.unsubscribe = undefined;
    this.terminal.off("pause", this.disableReporting);
    this.terminal.off("resume", this.enableReporting);
    this.onFocusChange = undefined;
    this.started = false;
    this.focused = true;
  }

  private readonly enableReporting = (): void => {
    if (!this.started || this.reporting) return;
    this.terminal.write(ENABLE_FOCUS_REPORTING);
    this.reporting = true;
  };

  private readonly disableReporting = (): void => {
    if (!this.reporting) return;
    this.terminal.write(DISABLE_FOCUS_REPORTING);
    this.reporting = false;
  };
}
