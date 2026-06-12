import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { ATTENTION_REQUEST, ATTENTION_RESOLVE } from "./attention.js";
import type { CompanionSession } from "./session.js";

export function registerCompanionHandlers(pi: ExtensionAPI, session: CompanionSession): void {
  pi.on("session_start", async (_event, ctx) => {
    if (session.isEnabled) await session.enable(ctx);
  });

  pi.events.on(ATTENTION_REQUEST, (data) => session.requestAttention(data));
  pi.events.on(ATTENTION_RESOLVE, (data) => session.resolveAttention(data));

  pi.on("agent_start", async (_event, ctx) => {
    session.noteContext(ctx);
    await session.starting();
  });

  pi.on("agent_end", async (_event, ctx) => {
    session.noteContext(ctx);
    session.done();
  });

  pi.on("message_update", async (_event, ctx) => {
    session.noteContext(ctx);
    session.thinking();
  });

  pi.on("tool_execution_start", async (event, ctx) => {
    session.noteContext(ctx);
    const args = (event.args ?? {}) as Record<string, string | undefined>;
    session.toolStart(event.toolName, args);
  });

  pi.on("tool_execution_end", async (event, ctx) => {
    session.noteContext(ctx);
    if (event.isError) session.toolError(event.toolName);
  });

  pi.on("turn_end", async (_event, ctx) => {
    session.noteContext(ctx);
    session.clearAttention();
  });

  pi.on("session_shutdown", async () => {
    session.shutdown();
  });
}
