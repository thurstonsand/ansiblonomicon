import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeEach, test } from "node:test";
import type { ExtensionCommandContext } from "@earendil-works/pi-coding-agent";
import { handleCodexCommand } from "./command.js";
import { DEFAULT_CODEX_SETTINGS, saveCodexSettings } from "./settings.js";

const agentDir = mkdtempSync(join(tmpdir(), "codexctl-"));
process.env.PI_CODING_AGENT_DIR = agentDir;

const CODEX_MODEL = { provider: "openai-codex", id: "gpt-x", api: "openai-codex-responses" };

function savedCodex(): unknown {
  return JSON.parse(readFileSync(join(agentDir, "settings.json"), "utf8")).codex;
}

/** A command context whose dialogs answer from `answers` in order, as an RPC host would. */
function host(mode: "rpc" | "tui", answers: string[]) {
  const asked: Array<{ title: string; options: string[] }> = [];
  const notices: Array<{ message: string; type?: string }> = [];
  let customCalls = 0;
  const ctx = {
    mode,
    hasUI: true,
    model: CODEX_MODEL,
    ui: {
      select: async (title: string, options: string[]) => {
        asked.push({ title, options });
        return answers.shift();
      },
      notify: (message: string, type?: string) => notices.push({ message, type }),
      custom: async () => {
        customCalls += 1;
        return undefined;
      },
    },
  } as unknown as ExtensionCommandContext;
  return { ctx, asked, notices, customCalls: () => customCalls };
}

beforeEach(() => saveCodexSettings(DEFAULT_CODEX_SETTINGS));

test("over RPC, a bare /codex asks through select and toggles fast priority", async () => {
  const rpc = host("rpc", ["Turn fast priority on"]);
  await handleCodexCommand("", rpc.ctx);

  assert.equal(rpc.customCalls(), 0);
  assert.equal(rpc.asked.length, 1);
  assert.match(rpc.asked[0]?.title ?? "", /^Codex settings\n/);
  assert.deepEqual(savedCodex(), { ...DEFAULT_CODEX_SETTINGS, fast: true });
});

test("over RPC, a setting's value comes from a second select that marks the current one", async () => {
  const rpc = host("rpc", ["Change verbosity (now low)", "high"]);
  await handleCodexCommand("", rpc.ctx);

  assert.deepEqual(rpc.asked[1]?.options, ["low (current)", "medium", "high"]);
  assert.deepEqual(savedCodex(), { ...DEFAULT_CODEX_SETTINGS, verbosity: "high" });
});

test("over RPC, a typed answer is read as /codex arguments", async () => {
  const rpc = host("rpc", ["summary off"]);
  await handleCodexCommand("", rpc.ctx);
  assert.deepEqual(savedCodex(), { ...DEFAULT_CODEX_SETTINGS, reasoningSummary: "off" });

  const typo = host("rpc", ["summary sometimes"]);
  await handleCodexCommand("", typo.ctx);
  assert.deepEqual(savedCodex(), { ...DEFAULT_CODEX_SETTINGS, reasoningSummary: "off" });
  assert.equal(typo.notices.at(-1)?.type, "error");
});

test("over RPC, keeping the current settings writes nothing", async () => {
  const rpc = host("rpc", ["Keep current settings"]);
  await handleCodexCommand("", rpc.ctx);
  assert.deepEqual(rpc.notices, []);
});

test("in the TUI, a bare /codex opens the panel", async () => {
  const tui = host("tui", []);
  await handleCodexCommand("", tui.ctx);
  assert.equal(tui.customCalls(), 1);
  assert.equal(tui.asked.length, 0);
});
