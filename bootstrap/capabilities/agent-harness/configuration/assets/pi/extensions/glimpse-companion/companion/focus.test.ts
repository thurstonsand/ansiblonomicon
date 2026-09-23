import assert from "node:assert/strict";
import { test } from "node:test";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import { type FocusTerminal, parseTerminalInput, TerminalFocusTracker } from "./focus.js";

type InputHandler = (data: string) => { consume?: boolean; data?: string } | undefined;
type FocusEvent = "pause" | "resume";

class FakeTerminal implements FocusTerminal {
  inputIsTTY = true;
  outputIsTTY = true;
  readonly writes: string[] = [];
  private readonly listeners = new Map<FocusEvent, Set<() => void>>();
  private readonly dataListeners = new Set<(data: string) => void>();

  write(data: string): void {
    this.writes.push(data);
  }

  on(event: FocusEvent, listener: () => void): void {
    const listeners = this.listeners.get(event) ?? new Set();
    listeners.add(listener);
    this.listeners.set(event, listeners);
  }

  off(event: FocusEvent, listener: () => void): void {
    this.listeners.get(event)?.delete(listener);
  }

  onData(listener: (data: string) => void): () => void {
    this.dataListeners.add(listener);
    return () => {
      this.dataListeners.delete(listener);
    };
  }

  emit(event: FocusEvent): void {
    for (const listener of this.listeners.get(event) ?? []) listener();
  }

  emitData(data: string): void {
    for (const listener of this.dataListeners) listener(data);
  }

  get dataListenerCount(): number {
    return this.dataListeners.size;
  }

  listenerCount(event: FocusEvent): number {
    return this.listeners.get(event)?.size ?? 0;
  }
}

function context(onInput: (handler: InputHandler) => () => void): ExtensionContext {
  return {
    mode: "tui",
    ui: { onTerminalInput: onInput },
  } as unknown as ExtensionContext;
}

test("removes terminal focus reports while preserving ordinary input", () => {
  assert.deepEqual(parseTerminalInput("\x1b[I"), {
    data: "",
    focused: true,
    includesFocusReport: true,
  });
  assert.deepEqual(parseTerminalInput("x\x1b[O"), {
    data: "x",
    focused: false,
    includesFocusReport: true,
  });
  assert.deepEqual(parseTerminalInput("\x1b[Ox"), {
    data: "x",
    focused: true,
    includesFocusReport: true,
  });
  assert.deepEqual(parseTerminalInput("x"), {
    data: "x",
    focused: true,
    includesFocusReport: false,
  });
});

test("tracks focus while terminal reporting is active", () => {
  const terminal = new FakeTerminal();
  const tracker = new TerminalFocusTracker(terminal);
  const changes: boolean[] = [];
  let inputHandler: InputHandler | undefined;
  let unsubscribed = false;

  tracker.start(
    context((handler) => {
      inputHandler = handler;
      return () => {
        unsubscribed = true;
        inputHandler = undefined;
      };
    }),
    (focused) => changes.push(focused),
  );

  assert.equal(tracker.isFocused, true);
  assert.deepEqual(terminal.writes, ["\x1b[?1004h"]);
  assert.equal(terminal.listenerCount("pause"), 1);
  assert.equal(terminal.listenerCount("resume"), 1);
  assert.equal(terminal.dataListenerCount, 1);

  terminal.emitData("\x1b[O");
  assert.equal(tracker.isFocused, false);
  assert.deepEqual(changes, [false]);

  terminal.emitData("\x1b[O");
  assert.deepEqual(changes, [false]);

  terminal.emitData("x");
  assert.equal(tracker.isFocused, true);
  assert.deepEqual(changes, [false, true]);

  terminal.emitData("x\x1b[O");
  assert.equal(tracker.isFocused, false);
  assert.deepEqual(changes, [false, true, false]);

  terminal.emitData("\x1b[Ix");
  assert.equal(tracker.isFocused, true);
  assert.deepEqual(changes, [false, true, false, true]);

  assert.deepEqual(inputHandler?.("\x1b[O"), { consume: true });
  assert.deepEqual(inputHandler?.("x\x1b[O"), { data: "x" });
  assert.equal(inputHandler?.("x"), undefined);
  assert.deepEqual(changes, [false, true, false, true]);

  terminal.emit("pause");
  terminal.emit("resume");
  tracker.stop();

  assert.deepEqual(terminal.writes, ["\x1b[?1004h", "\x1b[?1004l", "\x1b[?1004h", "\x1b[?1004l"]);
  assert.equal(terminal.listenerCount("pause"), 0);
  assert.equal(terminal.listenerCount("resume"), 0);
  assert.equal(terminal.dataListenerCount, 0);
  assert.equal(unsubscribed, true);
});
