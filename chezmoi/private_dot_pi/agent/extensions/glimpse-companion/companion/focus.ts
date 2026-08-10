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
  onData(listener: (data: string) => void): () => void;
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
  onData(listener) {
    const handler = (data: string | Buffer) => listener(data.toString());
    process.stdin.on("data", handler);
    return () => {
      process.stdin.off("data", handler);
    };
  },
};

export class TerminalFocusTracker {
  // DEC focus reporting has no current-state query. Assume focused so a missing
  // initial report preserves the normal Done expiry instead of pinning forever.
  private focused = true;
  private started = false;
  private reporting = false;
  private unsubscribeInput: (() => void) | undefined;
  private unsubscribeData: (() => void) | undefined;
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
    // Focus is read off raw stdin rather than the pi input chain: the
    // alternate-screen renderer registers its own listener first and consumes
    // focus reports, so an extension listener never sees them. The pi listener
    // is kept only to strip reports the main-screen renderer would otherwise
    // treat as typed input.
    this.unsubscribeData = this.terminal.onData(this.observe);
    this.unsubscribeInput = ctx.ui.onTerminalInput((data) => {
      const input = parseTerminalInput(data);
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
    this.unsubscribeInput?.();
    this.unsubscribeInput = undefined;
    this.unsubscribeData?.();
    this.unsubscribeData = undefined;
    this.terminal.off("pause", this.disableReporting);
    this.terminal.off("resume", this.enableReporting);
    this.onFocusChange = undefined;
    this.started = false;
    this.focused = true;
  }

  private readonly observe = (data: string): void => {
    const { focused } = parseTerminalInput(data);
    if (focused === this.focused) return;
    this.focused = focused;
    this.onFocusChange?.(focused);
  };

  // Only the main screen needs us to manage focus reporting; the alternate
  // screen already enables 1004 with its mouse tracking and clears it on
  // terminal stop. Toggling it there is redundant, and disabling on stop()
  // clears a mode pi still wants.
  // TODO: skip these writes under the alternate screen once pi exposes the tui
  // mode to extensions.
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
