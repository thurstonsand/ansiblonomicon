import { execFileSync, spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { connect, type Socket } from "node:net";
import { homedir } from "node:os";
import { basename, delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { getCompanionSocketPath } from "./socket-path.mjs";

interface FollowCursorSupport {
  supported: boolean;
  reason?: string;
}

interface CompanionMessage {
  id: string;
  project: string;
  status: string;
  detail?: string;
  contextPercent?: number;
}

interface CompanionSettings extends Record<string, unknown> {
  enabled?: boolean;
}

// glimpseui is installed as a global npm package, not under this extension's
// node_modules, so a bare import would not resolve at runtime. Locate its entry
// dynamically and import it lazily — this also keeps type-checking from
// requiring the package to be installed on machines that never run the
// companion (e.g. work hosts whose registry lacks glimpseui).
function resolveGlimpseEntry(): string | null {
  const candidates: string[] = [];
  const override = process.env.GLIMPSE_DIR;
  if (override) candidates.push(join(override, "src", "glimpse.mjs"));
  try {
    candidates.push(createRequire(import.meta.url).resolve("glimpseui"));
  } catch {}
  try {
    const root = execFileSync("npm", ["root", "-g"], { encoding: "utf-8" }).trim();
    if (root) candidates.push(join(root, "glimpseui", "src", "glimpse.mjs"));
  } catch {}
  return candidates.find((c) => existsSync(c)) ?? null;
}

// pi ships as a compiled binary, so process.execPath points at pi, not node.
// Spawning it would relaunch pi with companion.mjs as a prompt and recurse
// into an unbounded fan-out of sessions. Resolve a real node interpreter.
function resolveNode(): string | null {
  const override = process.env.GLIMPSE_NODE;
  if (override && existsSync(override)) return override;
  if (basename(process.execPath).toLowerCase().startsWith("node")) {
    return process.execPath;
  }
  const exe = process.platform === "win32" ? "node.exe" : "node";
  for (const dir of (process.env.PATH ?? "").split(delimiter)) {
    if (!dir) continue;
    const candidate = join(dir, exe);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

const SOCK = getCompanionSocketPath();
const SESSION_ID = randomUUID().slice(0, 8);
const COMPANION_PATH = join(fileURLToPath(new URL(".", import.meta.url)), "companion.mjs");
const SETTINGS_PATH = join(homedir(), ".pi", "companion.json");

function readSettings(): CompanionSettings {
  try {
    const parsed: unknown = JSON.parse(readFileSync(SETTINGS_PATH, "utf-8"));
    if (parsed && typeof parsed === "object") return parsed as CompanionSettings;
  } catch {}
  return {};
}

function loadEnabled(): boolean {
  return readSettings().enabled === true;
}

function saveEnabled(value: boolean) {
  try {
    const data = readSettings();
    data.enabled = value;
    writeFileSync(SETTINGS_PATH, `${JSON.stringify(data, null, 2)}\n`);
  } catch {}
}

export default function (pi: ExtensionAPI) {
  let enabled = loadEnabled();
  let sock: Socket | null = null;
  let lastStatus = "";
  let lastCtx: ExtensionContext | null = null;
  let warnedUnsupported = false;
  let followCursorSupport: FollowCursorSupport = { supported: true };
  let glimpseLoaded = false;
  const project = basename(process.cwd());

  async function loadGlimpse(): Promise<void> {
    if (glimpseLoaded) return;
    glimpseLoaded = true;
    const entry = resolveGlimpseEntry();
    if (!entry) {
      followCursorSupport = { supported: false, reason: "glimpseui not found" };
      return;
    }
    try {
      const mod = (await import(entry)) as {
        getFollowCursorSupport?: () => FollowCursorSupport;
      };
      if (typeof mod.getFollowCursorSupport === "function") {
        followCursorSupport = mod.getFollowCursorSupport();
      }
    } catch (err) {
      followCursorSupport = {
        supported: false,
        reason: err instanceof Error ? err.message : String(err),
      };
    }
  }

  // ── helpers ────────────────────────────────────────────────────────────────

  function maybeNotifyUnsupported(ctx: ExtensionContext) {
    if (followCursorSupport.supported || warnedUnsupported) return;
    warnedUnsupported = true;
    ctx.ui.notify(`Companion disabled on this platform: ${followCursorSupport.reason}`, "info");
  }

  function send(status: string, detail?: string) {
    lastStatus = status;
    if (!sock || sock.destroyed) return;
    const msg: CompanionMessage = { id: SESSION_ID, project, status, detail };
    if (lastCtx) {
      try {
        const usage = lastCtx.getContextUsage();
        if (usage && usage.percent != null) {
          msg.contextPercent = Math.round(usage.percent);
        }
      } catch {}
    }
    sock.write(`${JSON.stringify(msg)}\n`);
  }

  function sendRemove() {
    if (!sock || sock.destroyed) return;
    sock.write(`${JSON.stringify({ id: SESSION_ID, type: "remove" })}\n`);
    lastStatus = "";
  }

  function connectToCompanion(): Promise<void> {
    return new Promise((resolve) => {
      sock = connect(SOCK, () => resolve());
      sock.on("error", () => {
        sock = null;
        resolve();
      });
      sock.on("close", () => {
        sock = null;
      });
    });
  }

  async function ensureConnected() {
    if (sock && !sock.destroyed) return;

    // Try connecting to existing companion
    await connectToCompanion();
    if (sock) return;

    // Spawn companion and retry
    const node = resolveNode();
    if (!node) return;
    const child = spawn(node, [COMPANION_PATH], {
      detached: true,
      stdio: "ignore",
      windowsHide: process.platform === "win32",
    });
    child.unref();

    // Wait for socket to be available
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 100));
      await connectToCompanion();
      if (sock) return;
    }
  }

  function disconnect() {
    if (sock && !sock.destroyed) {
      sendRemove();
      sock.end();
    }
    sock = null;
    lastStatus = "";
  }

  // ── enable / disable ──────────────────────────────────────────────────────

  async function enable(ctx: ExtensionContext) {
    enabled = true;
    saveEnabled(true);
    await loadGlimpse();
    if (!followCursorSupport.supported) {
      maybeNotifyUnsupported(ctx);
      ctx.ui.setStatus("companion", undefined);
      return;
    }
    await ensureConnected();
    if (!sock && !resolveNode()) {
      ctx.ui.notify(
        "Companion needs a node interpreter on PATH (set GLIMPSE_NODE to override)",
        "info",
      );
    }
    const theme = ctx.ui.theme;
    ctx.ui.setStatus("companion", theme.fg("accent", "G") + theme.fg("dim", " ·"));
  }

  function disable(ctx: ExtensionContext) {
    enabled = false;
    saveEnabled(false);
    disconnect();
    ctx.ui.setStatus("companion", undefined);
  }

  // ── session start ─────────────────────────────────────────────────────────

  pi.on("session_start", async (_event, ctx) => {
    if (enabled) {
      await enable(ctx);
    }
  });

  // ── /companion command ────────────────────────────────────────────────────

  pi.registerCommand("companion", {
    description: "Toggle cursor companion (shows agent activity near cursor)",
    handler: async (_args, ctx) => {
      if (enabled) {
        disable(ctx);
        ctx.ui.notify("Companion disabled", "info");
      } else {
        await enable(ctx);
        if (followCursorSupport.supported) {
          ctx.ui.notify("Companion enabled", "info");
        }
      }
    },
  });

  // ── event handlers ────────────────────────────────────────────────────────

  pi.on("agent_start", async (_event, ctx) => {
    if (!enabled || !followCursorSupport.supported) return;
    lastCtx = ctx;
    await ensureConnected();
    send("starting");
  });

  pi.on("agent_end", async (_event, ctx) => {
    if (!enabled || !followCursorSupport.supported) return;
    lastCtx = ctx;
    send("done");
    setTimeout(() => {
      if (lastStatus === "done") sendRemove();
    }, 3000);
  });

  pi.on("message_update", async (_event, ctx) => {
    if (!enabled || !followCursorSupport.supported) return;
    lastCtx = ctx;
    if (lastStatus === "thinking") return;
    send("thinking");
  });

  pi.on("tool_execution_start", async (event, ctx) => {
    if (!enabled || !followCursorSupport.supported) return;
    lastCtx = ctx;
    const { toolName } = event;
    const args = (event.args ?? {}) as Record<string, string | undefined>;

    switch (toolName) {
      case "read":
        send("reading", basename(args.path ?? ""));
        break;
      case "edit":
      case "write":
        send("editing", basename(args.path ?? ""));
        break;
      case "bash":
        send("running", args.command ?? "");
        break;
      case "grep":
      case "find":
      case "ls":
        send("searching", args.pattern ?? args.path ?? "");
        break;
      default:
        send("running", toolName);
    }
  });

  pi.on("tool_execution_end", async (event, ctx) => {
    if (!enabled || !followCursorSupport.supported) return;
    lastCtx = ctx;
    if (event.isError) {
      send("error", event.toolName);
    }
  });

  pi.on("session_shutdown", async (_event, _ctx) => {
    disconnect();
  });
}
