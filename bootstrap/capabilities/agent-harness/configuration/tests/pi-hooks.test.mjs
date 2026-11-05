import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import timing from "../assets/pi/extensions/command-timing.ts";
import comments from "../assets/pi/extensions/no-chat-comments.ts";

function register(extension) {
  const handlers = {};
  extension({
    on: (name, handler) => {
      handlers[name] = handler;
    },
  });
  return handlers;
}

test("Pi timing preserves tool content and structured output at both warning boundaries", (t) => {
  let now = 0;
  t.mock.method(performance, "now", () => now);
  const hooks = register(timing);
  for (const [milliseconds, severity] of [
    [60000, "none"],
    [60001, "slow"],
    [300000, "slow"],
    [300001, "very slow"],
  ]) {
    now = 0;
    hooks.tool_call({ toolName: "bash", toolCallId: "call" });
    now = milliseconds;
    const result = hooks.tool_result({
      toolName: "bash",
      toolCallId: "call",
      content: [{ type: "text", text: "failure output" }],
      structuredContent: { exitCode: 7 },
      isError: true,
    });
    assert.deepEqual(result.content[0], { type: "text", text: "failure output" });
    assert.deepEqual(result.structuredContent, { exitCode: 7 });
    assert.equal(result.isError, undefined);
    const feedback = result.content[1].text;
    assert.equal(feedback.includes("Slow feedback loop:"), severity === "slow");
    assert.equal(feedback.includes("Very slow feedback loop:"), severity === "very slow");
    assert.equal(hooks.tool_result({ toolName: "bash", toolCallId: "call" }), undefined);
  }
  hooks.tool_call({ toolName: "bash", toolCallId: "abandoned" });
  hooks.session_start();
  assert.equal(hooks.tool_result({ toolName: "bash", toolCallId: "abandoned" }), undefined);
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
