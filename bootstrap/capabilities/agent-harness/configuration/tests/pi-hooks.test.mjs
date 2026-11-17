import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import timing from "../assets/pi/extensions/command-timing.ts";
import comments from "../assets/pi/extensions/no-chat-comments.ts";

function register(extension, sent = []) {
  const handlers = {};
  extension({
    on: (name, handler) => {
      handlers[name] = handler;
    },
    sendMessage: (message, options) => sent.push({ message, options }),
  });
  return handlers;
}

test("Pi timing steers the agent privately only when execution time crosses a warning boundary", () => {
  for (const [seconds, severity] of [
    [60, "none"],
    [60.1, "slow"],
    [300, "slow"],
    [300.1, "very slow"],
  ]) {
    const sent = [];
    const hooks = register(timing, sent);
    const result = hooks.tool_result({
      toolName: "bash",
      toolCallId: "call",
      content: [{ type: "text", text: "failure output" }],
      structuredContent: { exit_code: 7, wall_time_seconds: seconds },
      isError: true,
    });
    assert.equal(result, undefined);
    assert.equal(sent.length, severity === "none" ? 0 : 1);
    if (severity === "none") continue;
    const { message, options } = sent[0];
    assert.equal(message.display, false);
    assert.equal(options.deliverAs, "steer");
    assert.equal(message.content.includes("Slow feedback loop:"), severity === "slow");
    assert.equal(message.content.includes("Very slow feedback loop:"), severity === "very slow");
  }
});

test("Pi edit batches and writes reject new chat comments but retain unrelated content", async () => {
  const directory = await mkdtemp(join(tmpdir(), "pi-comments-"));
  const hooks = register(comments);
  try {
    for (const [text, blocked] of [
      ["// as requested", true],
      ["# Used to be x; now y", true],
      ["// Retries need a stable request ID.", false],
      ['const text = "// as requested";', false],
    ]) {
      for (const [toolName, input] of [
        ["edit", { path: "example.ts", edits: [{ oldText: "old", newText: text }] }],
        ["write", { path: "example.ts", content: text }],
      ]) {
        const result = await hooks.tool_call({ toolName, input }, { cwd: directory });
        assert.equal(result?.block === true, blocked);
      }
    }
    await writeFile(join(directory, "example.ts"), "// as requested\nconst x = 1;");
    assert.equal(
      await hooks.tool_call(
        {
          toolName: "write",
          input: { path: "example.ts", content: "// as requested\nconst x = 2;" },
        },
        { cwd: directory },
      ),
      undefined,
    );
    assert.equal(
      await hooks.tool_call(
        {
          toolName: "edit",
          input: {
            path: "example.ts",
            edits: [
              {
                oldText: "// as requested\nconst x = 1;",
                newText: "// as requested\nconst x = 2;",
              },
            ],
          },
        },
        { cwd: directory },
      ),
      undefined,
    );
  } finally {
    await rm(directory, { recursive: true });
  }
});
