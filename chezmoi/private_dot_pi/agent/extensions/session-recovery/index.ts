import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import {
  deleteIgnoredRecords,
  deleteRecord,
  loadSettings,
  type Settings,
  writeRecord,
} from "@thurstons/session-recovery";

// Pi funnels both deliberate quits (/quit, Ctrl-D, Ctrl-C ×2) and
// signal-driven shutdowns (tab close, SIGHUP/SIGTERM, reboot) through the same
// teardown, emitting reason "quit" for all of them. The only discriminator is
// the OS signal, which pi consumes internally and does not expose on the event.
// We recover it by registering our own signal listeners ahead of pi's: pi
// registers its SIGTERM/SIGHUP handlers exactly once at init and drives the
// session_shutdown emission synchronously inside that handler, so a listener
// prepended ahead of it sets this flag before our shutdown handler reads it.
let viaSignal = false;
let signalHooksInstalled = false;

function installSignalHooks(): void {
  if (signalHooksInstalled) {
    return;
  }
  signalHooksInstalled = true;
  const mark = (): void => {
    viaSignal = true;
  };
  // SIGHUP and SIGTERM only: pi already owns these, so prepending a flag-setter
  // does not change process-termination behavior. SIGINT is deliberately left
  // alone — the TUI reads Ctrl-C as a keystroke, and adding a listener would
  // suppress Node's default SIGINT termination.
  process.prependListener("SIGHUP", mark);
  process.prependListener("SIGTERM", mark);
}

function record(pi: ExtensionAPI, ctx: ExtensionContext, settings: Settings): void {
  const transcript = ctx.sessionManager.getSessionFile();
  if (!transcript || !ctx.hasUI) {
    return;
  }
  writeRecord(
    {
      tool: "pi",
      sessionId: ctx.sessionManager.getSessionId(),
      name: pi.getSessionName() ?? null,
      cwd: ctx.cwd,
      transcript,
      pid: process.pid,
    },
    settings,
  );
}

export default function sessionRecovery(pi: ExtensionAPI): void {
  const settings = loadSettings();

  pi.on("session_start", async (_event, ctx) => {
    installSignalHooks();
    deleteIgnoredRecords(settings);
    record(pi, ctx, settings);
  });

  pi.on("agent_end", async (_event, ctx) => {
    record(pi, ctx, settings);
  });

  pi.on("session_shutdown", async (event, ctx) => {
    const sessionId = ctx.sessionManager.getSessionId();

    // "new"/"resume"/"fork" replace this session id in-process; the successor
    // writes its own record on session_start, so the old one is hidden from the
    // active/orphaned view but remains resumable by explicit name or id.
    if (event.reason === "new" || event.reason === "resume" || event.reason === "fork") {
      deleteRecord("pi", sessionId);
      return;
    }

    // "reload" keeps the same session id and is immediately followed by a
    // session_start that rewrites the record — leave it in place.
    if (event.reason === "reload") {
      return;
    }

    // reason === "quit": hide only on a deliberate in-app quit. A signal-driven
    // shutdown (tab close, SIGHUP/SIGTERM, reboot) is left behind as a
    // recoverable orphan.
    if (!viaSignal) {
      deleteRecord("pi", sessionId);
    }
  });
}
