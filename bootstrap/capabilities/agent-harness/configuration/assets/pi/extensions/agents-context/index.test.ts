import { deepStrictEqual, equal, match } from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import type {
  BeforeAgentStartEvent,
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import agentsContext from "./index.js";

test("adds referenced files as a prompt section without forcing the rendered prompt", () => {
  const cwd = mkdtempSync(join(tmpdir(), "agents-context-"));
  try {
    const agentsPath = join(cwd, "AGENTS.md");
    writeFileSync(agentsPath, "See @details.md");
    writeFileSync(join(cwd, "details.md"), "Extra instructions");

    let handler: ((event: BeforeAgentStartEvent, ctx: ExtensionContext) => unknown) | undefined;
    agentsContext({
      on(_event: string, callback: typeof handler) {
        handler = callback;
        return () => {};
      },
    } as unknown as ExtensionAPI);

    const systemPromptOptions = {
      cwd,
      contextFiles: [{ path: agentsPath, content: "See @details.md" }],
      sections: {},
    } as BeforeAgentStartEvent["systemPromptOptions"];
    const systemPrompt = "Pi's original prompt";
    const result = handler?.(
      { type: "before_agent_start", prompt: "Hi", systemPrompt, systemPromptOptions },
      { cwd, ui: { notify() {} } } as unknown as ExtensionContext,
    );

    equal(result, undefined);
    deepStrictEqual(Object.keys(systemPromptOptions.sections), ["agents_context"]);
    match(systemPromptOptions.sections.agents_context, /Extra instructions/);
    equal(systemPromptOptions.forceSystemPrompt, undefined);
    equal(systemPrompt.includes("Extra instructions"), false);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
});
