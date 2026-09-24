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

function activeSession(focused: boolean): {
  session: CompanionSession;
  messages: Array<Record<string, unknown>>;
  focusChanged: (focused: boolean) => void;
} {
  const messages: Array<Record<string, unknown>> = [];
  const session = Object.assign(Object.create(CompanionSession.prototype), {
    enabled: true,
    followCursorSupport: { supported: true },
    attention: { active: false, clear: () => false },
    focus: { isFocused: focused },
    connection: {
      isConnected: true,
      async ensureConnected() {},
      write(message: Record<string, unknown>) {
        messages.push(message);
      },
    },
    lastStatus: "",
    lastCtx: null,
    doneNeedsAcknowledgement: false,
  }) as CompanionSession;
  const focusChanged = (session as unknown as { focusChanged: (focused: boolean) => void })
    .focusChanged;
  return { session, messages, focusChanged: focusChanged.bind(session) };
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

test("passes the compaction reason through the compaction lifecycle", async () => {
  const compactedReasons: string[] = [];
  const session = {
    isEnabled: false,
    noteContext() {},
    compacted(reason: string) {
      compactedReasons.push(reason);
    },
  } as unknown as CompanionSession;
  const handlers = registerHandlers(session);
  const compacted = handlerFor(handlers, "session_compact");

  await compacted({ reason: "manual" } as never, context(false));
  await compacted({ reason: "threshold" } as never, context(false));

  assert.deepEqual(compactedReasons, ["manual", "threshold"]);
});

test("manual compaction completes while automatic compaction defers to agent_settled", () => {
  let doneCount = 0;
  const session = Object.assign(Object.create(CompanionSession.prototype), {
    enabled: true,
    followCursorSupport: { supported: true },
    done() {
      doneCount += 1;
    },
  }) as CompanionSession;

  session.compacted("threshold");
  session.compacted("overflow");
  assert.equal(doneCount, 0);

  session.compacted("manual");
  assert.equal(doneCount, 1);
});

test("removes compaction status when compaction fails", async () => {
  const { session, messages } = activeSession(true);
  const handlers = registerHandlers(session);

  await session.compacting("manual");
  assert.equal(messages.length, 1);
  assert.equal(messages[0]?.status, "compacting");

  await handlerFor(handlers, "session_compact_failed")(
    { reason: "manual", aborted: false, errorMessage: "boom" } as never,
    context(true),
  );
  assert.equal(messages.length, 2);
  assert.equal(messages[1]?.type, "remove");
});

test("leaves unrelated status alone when compaction fails", async () => {
  const { session, messages } = activeSession(true);
  const handlers = registerHandlers(session);

  session.thinking();
  assert.equal(messages.length, 1);
  assert.equal(messages[0]?.status, "thinking");

  await handlerFor(handlers, "session_compact_failed")(
    { reason: "threshold", aborted: true } as never,
    context(false),
  );
  assert.equal(messages.length, 1);
});

test("pins completion while unfocused until focus acknowledges it", () => {
  const { session, messages, focusChanged } = activeSession(false);

  session.done();
  assert.equal(messages.length, 1);
  assert.equal(messages[0]?.status, "done");
  assert.equal(messages[0]?.acknowledgementPending, true);

  focusChanged(true);
  assert.equal(messages.length, 2);
  assert.equal(messages[1]?.type, "remove");
});

test("pins a visible completion when focus leaves before its timeout", () => {
  const { session, messages, focusChanged } = activeSession(true);

  session.done();
  focusChanged(false);
  assert.equal(messages.length, 2);
  assert.equal(messages[1]?.acknowledgementPending, true);

  focusChanged(true);
  assert.equal(messages.length, 3);
  assert.equal(messages[2]?.type, "remove");
});
