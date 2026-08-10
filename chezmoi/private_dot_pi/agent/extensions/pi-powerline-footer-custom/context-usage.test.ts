import assert from "node:assert/strict";
import { test } from "node:test";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";

import { ContextUsageCache, estimateUnknownContextUsage } from "./context-usage.js";

test("estimates the active compacted context when Pi reports unknown usage", () => {
  const ctx = {
    getContextUsage: () => ({ tokens: null, contextWindow: 100, percent: null }),
    getSystemPrompt: () => "12345678",
    sessionManager: {
      buildContextEntries: () => [
        {
          type: "message",
          id: "message-1",
          parentId: null,
          timestamp: "2026-08-10T00:00:00.000Z",
          message: { role: "user", content: "12345678", timestamp: 0 },
        },
      ],
    },
  } as unknown as ExtensionContext;

  assert.deepEqual(estimateUnknownContextUsage(ctx), {
    tokens: 4,
    contextWindow: 100,
  });
});

test("does not estimate over known provider usage", () => {
  const ctx = {
    getContextUsage: () => ({ tokens: 25, contextWindow: 100, percent: 25 }),
  } as unknown as ExtensionContext;

  assert.equal(estimateUnknownContextUsage(ctx), undefined);
});

test("caches known usage until the session leaf changes", () => {
  let leafId = "leaf-1";
  let reads = 0;
  const ctx = {
    getContextUsage() {
      reads++;
      return { tokens: reads * 10, contextWindow: 100, percent: reads * 10 };
    },
    sessionManager: {
      getLeafId: () => leafId,
    },
  } as unknown as ExtensionContext;
  const cache = new ContextUsageCache();

  assert.equal(cache.get(ctx)?.tokens, 10);
  assert.equal(cache.get(ctx)?.tokens, 10);
  leafId = "leaf-2";
  assert.equal(cache.get(ctx)?.tokens, 20);
  assert.equal(reads, 2);
});
