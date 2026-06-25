import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, unlinkSync } from "node:fs";
import { createRequire } from "node:module";
import { createServer, type Socket } from "node:net";
import { join } from "node:path";
import { createInterface } from "node:readline";
// This file runs as a standalone process via `node companion.ts`, not through
// pi's loader, so runtime imports must name the real `.ts` file for Node to resolve.
import type { CompanionMessage, CompanionUpdateMessage } from "./shared/messages.ts";
import { getCompanionSocketPath, usesNamedPipe } from "./shared/socket-path.ts";

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

const glimpseEntry = resolveGlimpseEntry();
if (!glimpseEntry) {
  console.error("glimpse companion: glimpseui not found (set GLIMPSE_DIR to override)");
  process.exit(1);
}
// glimpseui has no published types and is resolved dynamically at runtime.
// biome-ignore lint/suspicious/noExplicitAny: external module without type declarations.
const { open } = (await import(glimpseEntry)) as { open: (...args: any[]) => any };

const SOCK = getCompanionSocketPath();

const WINDOW_WIDTH = 630;
const MIN_WINDOW_HEIGHT = 100;
const MAX_VISIBLE_SESSIONS = 6;
const DEFAULT_FONT_FAMILY = "Menlo";

function loadCompanionFontFamily(): string {
  try {
    const fontFamily = readFileSync(
      new URL("./companion/font-family.txt", import.meta.url),
      "utf-8",
    ).trim();
    return fontFamily || DEFAULT_FONT_FAMILY;
  } catch {
    return DEFAULT_FONT_FAMILY;
  }
}

// ── HTML ──────────────────────────────────────────────────────────────────────

interface CompanionClientConfig {
  maxVisibleSessions: number;
  fontFamily: string;
}

function safeInlineJSON(data: unknown): string {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026");
}

function readClientAsset(fileName: string): string {
  return readFileSync(new URL(`./companion/client/${fileName}`, import.meta.url), "utf-8");
}

function renderClientTemplate(values: Record<string, string>): string {
  let html = readClientAsset("index.html");
  for (const [key, value] of Object.entries(values)) {
    const token = `{{${key}}}`;
    html = html.replaceAll(`/* ${token} */`, value).replaceAll(`{ "${token}": true }`, value);
  }
  if (/{{[A-Z_]+}}/.test(html)) {
    throw new Error("Unresolved companion client template token");
  }
  return html;
}

function buildHTML(): string {
  const config: CompanionClientConfig = {
    maxVisibleSessions: MAX_VISIBLE_SESSIONS,
    fontFamily: loadCompanionFontFamily(),
  };

  return renderClientTemplate({
    COMPANION_CSS: readClientAsset("styles.css"),
    COMPANION_CONFIG: safeInlineJSON(config),
    COMPANION_JS: readClientAsset("app.js"),
  });
}

// ── state ─────────────────────────────────────────────────────────────────────

const agents = new Map<string, CompanionUpdateMessage>();
const sockets = new Set<Socket>();
// biome-ignore lint/suspicious/noExplicitAny: glimpse window handle is untyped.
let win: any = null;
let winReady = false;
let pendingUpdates: string[] = [];
let idleTimer: ReturnType<typeof setTimeout> | null = null;

function resetIdleTimer(): void {
  if (idleTimer) clearTimeout(idleTimer);
  idleTimer = setTimeout(() => {
    if (agents.size === 0 && sockets.size === 0) {
      cleanup();
      process.exit(0);
    }
  }, 5000);
}

// ── render ─────────────────────────────────────────────────────────────────────

function pushUpdate(id: string, data: CompanionUpdateMessage): void {
  const update = { ...data, id };
  const js = `window.Companion.update(${safeInlineJSON(update)})`;
  if (winReady) win.send(js);
  else pendingUpdates.push(js);
}

function pushRemove(id: string): void {
  const js = `window.Companion.remove(${safeInlineJSON(id)})`;
  if (winReady) win.send(js);
  else pendingUpdates.push(js);
}

// ── socket server ─────────────────────────────────────────────────────────────

// Clean up stale socket (not needed for Windows named pipes)
if (!usesNamedPipe(SOCK)) {
  try {
    unlinkSync(SOCK);
  } catch {}
}

const server = createServer((socket) => {
  sockets.add(socket);
  const rl = createInterface({ input: socket, crlfDelay: Number.POSITIVE_INFINITY });
  let clientId: string | null = null;

  rl.on("line", (line) => {
    try {
      const msg = JSON.parse(line) as CompanionMessage;
      if (!msg.id) return;
      clientId = msg.id;

      if (msg.type === "remove") {
        agents.delete(clientId);
        pushRemove(clientId);
        resetIdleTimer();
        return;
      }

      agents.set(clientId, msg);
      pushUpdate(clientId, msg);
      resetIdleTimer();
    } catch {}
  });

  socket.on("close", () => {
    sockets.delete(socket);
    if (clientId) {
      agents.delete(clientId);
      pushRemove(clientId);
    }
    resetIdleTimer();
  });

  socket.on("error", () => {});
});

server.listen(SOCK, () => {
  // Socket ready
});

// ── window ────────────────────────────────────────────────────────────────────

win = open(buildHTML(), {
  width: WINDOW_WIDTH,
  height: MIN_WINDOW_HEIGHT,
  frameless: true,
  floating: true,
  transparent: true,
  clickThrough: true,
  noDock: true,
  followCursor: true,
  followMode: "spring",
  cursorAnchor: "top-right",
});

win.on("ready", () => {
  winReady = true;
  for (const js of pendingUpdates) win.send(js);
  pendingUpdates = [];
  resetIdleTimer();
});

win.on("message", (data: unknown) => {
  if (!data || typeof data !== "object") return;
  const message = data as { type?: unknown; height?: unknown };
  if (message.type !== "resize" || typeof message.height !== "number") return;
  const height = Math.max(MIN_WINDOW_HEIGHT, Math.ceil(message.height));
  if (typeof win.resize === "function") {
    win.resize(WINDOW_WIDTH, height);
  } else if (typeof win._write === "function") {
    win._write({ type: "resize", width: WINDOW_WIDTH, height });
  }
});

win.on("closed", () => {
  cleanup();
  process.exit(0);
});
win.on("error", () => {});

// ── cleanup ───────────────────────────────────────────────────────────────────

let cleanedUp = false;
function cleanup(): void {
  if (cleanedUp) return;
  cleanedUp = true;
  server.close();
  if (!usesNamedPipe(SOCK)) {
    try {
      unlinkSync(SOCK);
    } catch {}
  }
  if (win)
    try {
      win.close();
    } catch {}
}

process.on("SIGTERM", () => {
  cleanup();
  process.exit(0);
});
process.on("SIGINT", () => {
  cleanup();
  process.exit(0);
});
process.on("exit", cleanup);
