import assert from "node:assert/strict";
import { tmpdir } from "node:os";
import { test } from "node:test";
import { setTimeout as sleep } from "node:timers/promises";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import sessionTitle from "./session-title.ts";

type Handler = (event: unknown, ctx: ExtensionContext) => void;

// Like Pi's, the ctx throws on every access once its session has been disposed.
function startSession() {
  const handlers = new Map<string, Handler>();
  const pi = { on: (event: string, handler: Handler) => handlers.set(event, handler) };
  sessionTitle(pi as unknown as ExtensionAPI);

  const titles: string[] = [];
  let disposed = false;
  const ui = { setTitle: (title: string) => titles.push(title) };
  const ctx = {
    get cwd() {
      if (disposed) throw new Error("stale ctx");
      return tmpdir();
    },
    get ui() {
      if (disposed) throw new Error("stale ctx");
      return ui;
    },
  } as unknown as ExtensionContext;

  const emit = (event: string) => handlers.get(event)?.({ type: event }, ctx);
  emit("session_start");
  return {
    titles,
    shutDown: () => {
      emit("session_shutdown");
      disposed = true;
    },
  };
}

test("the title is set again after Pi's own startup title", async () => {
  const session = startSession();
  await sleep(10);
  assert.equal(session.titles.length, 2);
});

test("a session that ends before the deferred title does not touch its stale ctx", async () => {
  const session = startSession();
  session.shutDown();
  await sleep(10);
  assert.equal(session.titles.length, 1);
});
