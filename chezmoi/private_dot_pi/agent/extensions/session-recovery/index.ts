import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { deleteRecord, writeRecord } from "@thurstons/session-recovery";

function record(pi: ExtensionAPI, ctx: ExtensionContext): void {
  const transcript = ctx.sessionManager.getSessionFile();
  if (!transcript || !ctx.hasUI) {
    return;
  }
  writeRecord({
    tool: "pi",
    sessionId: ctx.sessionManager.getSessionId(),
    name: pi.getSessionName() ?? null,
    cwd: ctx.cwd,
    transcript,
    pid: process.pid,
  });
}

export default function sessionRecovery(pi: ExtensionAPI): void {
  pi.on("session_start", async (_event, ctx) => {
    record(pi, ctx);
  });

  pi.on("agent_end", async (_event, ctx) => {
    record(pi, ctx);
  });

  pi.on("session_shutdown", async (_event, ctx) => {
    deleteRecord("pi", ctx.sessionManager.getSessionId());
  });
}
