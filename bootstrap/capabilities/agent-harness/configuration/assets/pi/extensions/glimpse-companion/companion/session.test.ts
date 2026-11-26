import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import { CompanionSession } from "./session.js";

process.env.PI_CODING_AGENT_DIR = mkdtempSync(join(tmpdir(), "glimpse-companion-"));

/** A session whose glimpse window and socket are stubbed out, enabled from a host in `mode`. */
async function enableIn(mode: "rpc" | "tui") {
  const session = new CompanionSession();
  Object.assign(session, {
    glimpseLoaded: true,
    followCursorSupport: { supported: true },
    focus: { start() {}, stop() {}, isFocused: true },
    connection: {
      isConnected: true,
      async ensureConnected() {},
      write() {},
      end() {},
    },
  });
  const statuses = new Map<string, string | undefined>();
  const ctx = {
    mode,
    ui: {
      theme: { fg: (_color: string, text: string) => text },
      setStatus: (key: string, text: string | undefined) => statuses.set(key, text),
      notify() {},
    },
  } as unknown as ExtensionContext;
  await session.enable(ctx);
  return statuses;
}

test("the footer marker shows in the TUI but not on an RPC host's status line", async () => {
  assert.equal((await enableIn("tui")).get("companion"), "G ·");
  assert.equal((await enableIn("rpc")).has("companion"), false);
});
