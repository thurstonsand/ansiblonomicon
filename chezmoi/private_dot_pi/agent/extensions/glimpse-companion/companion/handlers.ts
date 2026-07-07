import type { AssistantMessageEvent } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type { TextUpdate, ThinkingUpdate, ToolCallUpdate } from "./activity.js";
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

  pi.on("message_update", async (event, ctx) => {
    session.noteContext(ctx);
    const update = event.assistantMessageEvent;
    if (isThinkingUpdate(update)) {
      session.thinking();
      return;
    }
    if (isTextUpdate(update)) {
      session.responding();
      return;
    }
    if (isToolCallUpdate(update)) {
      session.toolCallUpdate(update);
      return;
    }
  });

  pi.on("tool_execution_start", async (event, ctx) => {
    session.noteContext(ctx);
    const args = (event.args ?? {}) as Record<string, unknown>;
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

  pi.on("session_before_compact", async (event, ctx) => {
    session.noteContext(ctx);
    await session.compacting(event.reason);
  });

  pi.on("session_compact", async (_event, ctx) => {
    session.noteContext(ctx);
    session.compacted(ctx.isIdle());
  });

  pi.on("session_shutdown", async () => {
    session.shutdown();
  });
}

function isThinkingUpdate(update: AssistantMessageEvent): update is ThinkingUpdate {
  return (
    update.type === "thinking_start" ||
    update.type === "thinking_delta" ||
    update.type === "thinking_end"
  );
}

function isTextUpdate(update: AssistantMessageEvent): update is TextUpdate {
  return update.type === "text_start" || update.type === "text_delta" || update.type === "text_end";
}

function isToolCallUpdate(update: AssistantMessageEvent): update is ToolCallUpdate {
  return (
    update.type === "toolcall_start" ||
    update.type === "toolcall_delta" ||
    update.type === "toolcall_end"
  );
}
