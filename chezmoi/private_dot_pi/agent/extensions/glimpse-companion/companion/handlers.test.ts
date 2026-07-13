import assert from "node:assert/strict";
import { test } from "node:test";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { registerCompanionHandlers } from "./handlers.js";
import { CompanionSession } from "./session.js";

type Handler = (event: never, ctx: ExtensionContext) => Promise<void> | void;

function registerHandlers(session: CompanionSession): Map<string, Handler> {
  const handlers = new Map<string, Handler>();
  const pi = {
    on(name: string, handler: Handler) {
      handlers.set(name, handler);
    },
    events: { on() {} },
  } as unknown as ExtensionAPI;

  registerCompanionHandlers(pi, session);
  return handlers;
}

function handlerFor(handlers: Map<string, Handler>, name: string): Handler {
  const handler = handlers.get(name);
  assert.ok(handler, `expected ${name} handler`);
  return handler;
}

function context(isIdle: boolean): ExtensionContext {
  return { isIdle: () => isIdle } as unknown as ExtensionContext;
}

test("waits for agent settlement before marking queued work done", async () => {
  let doneCount = 0;
  const session = {
    isEnabled: false,
    noteContext() {},
    async starting() {},
    done() {
      doneCount += 1;
    },
  } as unknown as CompanionSession;
  const handlers = registerHandlers(session);

  assert.equal(handlers.has("agent_end"), false);
  await handlerFor(handlers, "agent_start")(undefined as never, context(false));
  assert.equal(doneCount, 0);

  await handlerFor(handlers, "agent_settled")(undefined as never, context(true));
  assert.equal(doneCount, 1);
});

test("passes idle state through the compaction lifecycle", async () => {
  const compactedStates: boolean[] = [];
  const session = {
    isEnabled: false,
    noteContext() {},
    compacted(isIdle: boolean) {
      compactedStates.push(isIdle);
    },
  } as unknown as CompanionSession;
  const handlers = registerHandlers(session);
  const compacted = handlerFor(handlers, "session_compact");

  await compacted(undefined as never, context(false));
  await compacted(undefined as never, context(true));

  assert.deepEqual(compactedStates, [false, true]);
});

test("manual idle compaction completes while active-run compaction does not", () => {
  let doneCount = 0;
  const session = Object.assign(Object.create(CompanionSession.prototype), {
    enabled: true,
    followCursorSupport: { supported: true },
    done() {
      doneCount += 1;
    },
  }) as CompanionSession;

  session.compacted(false);
  assert.equal(doneCount, 0);

  session.compacted(true);
  assert.equal(doneCount, 1);
});
