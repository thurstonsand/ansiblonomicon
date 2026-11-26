import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import powerlineFooterCustom from "./index.ts";

process.env.PI_CODING_AGENT_DIR = mkdtempSync(join(tmpdir(), "powerline-custom-"));

type Handler = (event: unknown, ctx: ExtensionContext) => unknown;

test("an RPC host gets only the budget status, never the footer-only items", async () => {
  const handlers = new Map<string, Handler>();
  powerlineFooterCustom({
    on: (event: string, handler: Handler) => handlers.set(event, handler),
    registerCommand() {},
  } as unknown as ExtensionAPI);

  const published = new Set<string>();
  const ctx = {
    mode: "rpc",
    cwd: tmpdir(),
    model: { provider: "openai", id: "gpt-x", name: "GPT X", contextWindow: 100_000 },
    getContextUsage: () => ({ tokens: 1_000, contextWindow: 100_000, percent: 1 }),
    sessionManager: { getBranch: () => [], getEntries: () => [] },
    ui: {
      theme: { fg: (_color: string, text: string) => text },
      setStatus: (key: string) => published.add(key),
    },
  } as unknown as ExtensionContext;

  for (const event of [
    "session_start",
    "model_select",
    "message_end",
    "turn_end",
    "agent_settled",
  ]) {
    await handlers.get(event)?.({ type: event, reason: "startup" }, ctx);
  }
  await handlers.get("tool_result")?.({ type: "tool_result", toolName: "bash", input: {} }, ctx);
  await new Promise((resolve) => setTimeout(resolve, 50));
  handlers.get("session_shutdown")?.({ type: "session_shutdown" }, ctx);

  assert.deepEqual([...published], ["cost_budget"]);
});
