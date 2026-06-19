import { execFileSync } from "node:child_process";
import { existsSync, unlinkSync } from "node:fs";
import { createRequire } from "node:module";
import { createServer, type Socket } from "node:net";
import { join } from "node:path";
import { createInterface } from "node:readline";
// This file runs as a standalone process via `node companion.ts`, not through
// pi's loader, so the import must name the real `.ts` file for Node to resolve.
import { getCompanionSocketPath, usesNamedPipe } from "./shared/socket-path.ts";

interface AgentMessage {
  id: string;
  project?: string;
  status?: string;
  detail?: string;
  contextPercent?: number;
  attention?: boolean;
  attentionLabel?: string;
  type?: string;
}

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

// ── status config ─────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  starting: "#22C55E",
  thinking: "#F59E0B",
  reading: "#3B82F6",
  editing: "#FACC15",
  running: "#F97316",
  searching: "#8B5CF6",
  done: "#22C55E",
  error: "#EF4444",
};

const STATUS_LABEL: Record<string, string> = {
  thinking: "Working",
  reading: "Reading",
  editing: "Editing",
  running: "Running",
  searching: "Searching",
  done: "Done",
  error: "Error",
};

const WINDOW_WIDTH = 630;
const MIN_WINDOW_HEIGHT = 100;
const WINDOW_VERTICAL_PADDING = 32;

// ── HTML ──────────────────────────────────────────────────────────────────────

function esc(s: string): string {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function truncate(s: string, max = 100): string {
  if (!s) return "";
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

function buildHTML(): string {
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: transparent !important;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 11px;
  font-weight: 600;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  font-optical-sizing: auto;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  height: 100vh;
  padding: 16px;
}
#pill {
  width: fit-content;
  max-width: calc(100vw - 32px);
  background: rgba(0,0,0,0.45);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  border-radius: 8px;
  padding: 2px 0;
  overflow: hidden;
  transition: opacity 0.3s ease-out;
}
.row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 4px 10px;
}
.dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 0.2s ease;
}
.project {
  color: rgba(255,255,255,0.95);
  font-weight: 500;
  flex-shrink: 0;
}
.sep { color: rgba(255,255,255,0.5); flex-shrink: 0; }
.status { color: rgba(255,255,255,0.9); flex-shrink: 0; }
.attention-label {
  color: #E9D5FF;
  flex-shrink: 0;
}
.detail {
  color: rgba(255,255,255,0.75);
  font-family: ui-monospace, 'SF Mono', monospace;
  font-size: 10px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@keyframes entry-attn-pulse {
  0%, 100% { background: rgba(0,0,0,0); }
  50% { background: rgba(0,0,0,0.24); }
}
.entry.attention {
  animation: entry-attn-pulse 1.5s ease-in-out infinite;
  border-radius: 2px;
}
.entry.attention:first-child { border-top-left-radius: 7px; border-top-right-radius: 7px; }
.entry.attention:last-child { border-bottom-left-radius: 7px; border-bottom-right-radius: 7px; }
@keyframes dot-attn-pulse {
  0%, 100% { box-shadow: 0 0 4px 1px rgba(192,132,252,0.45); }
  50% { box-shadow: 0 0 10px 3px rgba(192,132,252,0.9), 0 0 18px 5px rgba(168,85,247,0.35); }
}
.row.attention .dot {
  background: #C084FC !important;
  animation: dot-attn-pulse 1.5s ease-in-out infinite;
}
.meta {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px 4px 21px;
  font-size: 10px;
  font-weight: 500;
  color: rgba(255,255,255,0.85);
  font-family: ui-monospace, 'SF Mono', monospace;
}
.meta-sep { margin: 0 2px; }
</style>
</head>
<body>
<div id="pill"></div>
<script>
var _rows = {};
var _startTimes = {};
var _frozenElapsed = {};
var _tickTimer = null;

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function fmtElapsed(ms) {
  var s = Math.floor(ms / 1000);
  if (s < 60) return s + 's';
  var m = Math.floor(s / 60);
  s = s % 60;
  return m + 'm ' + (s < 10 ? '0' : '') + s + 's';
}

function startTick() {
  if (_tickTimer) return;
  _tickTimer = setInterval(function() {
    var ids = Object.keys(_rows);
    if (ids.length === 0) { clearInterval(_tickTimer); _tickTimer = null; return; }
    for (var i = 0; i < ids.length; i++) {
      if (_frozenElapsed[ids[i]]) continue;
      var el = document.getElementById('elapsed-' + ids[i]);
      if (el && _startTimes[ids[i]]) {
        el.textContent = fmtElapsed(Date.now() - _startTimes[ids[i]]);
      }
    }
  }, 1000);
}

function update(id, dotColor, project, status, detail, contextPercent, attention, attentionLabel) {
  if (!_startTimes[id]) _startTimes[id] = Date.now();
  if (status === 'Done' && _startTimes[id] && !_frozenElapsed[id]) {
    _frozenElapsed[id] = fmtElapsed(Date.now() - _startTimes[id]);
  }
  _rows[id] = { dotColor: dotColor, project: project, status: status, detail: detail, contextPercent: contextPercent, attention: attention, attentionLabel: attentionLabel };
  render();
  startTick();
}

function remove(id) {
  delete _rows[id];
  delete _startTimes[id];
  delete _frozenElapsed[id];
  render();
}

function render() {
  var pill = document.getElementById('pill');
  var ids = Object.keys(_rows);
  if (ids.length === 0) {
    pill.style.opacity = '0';
    pill.className = '';
    setTimeout(function() { pill.innerHTML = ''; }, 350);
    return;
  }
  pill.style.opacity = '1';
  var html = '';
  for (var i = 0; i < ids.length; i++) {
    var r = _rows[ids[i]];
    html += '<div id="r-' + ids[i] + '" class="' + (r.attention ? 'entry attention' : 'entry') + '">';
    html += '<div class="' + (r.attention ? 'row attention' : 'row') + '">';
    html += '<div class="dot" style="background:' + r.dotColor + '"></div>';
    html += '<span class="project">' + esc(r.project) + '</span>';
    if (r.attentionLabel) {
      html += '<span class="sep">·</span>';
      html += '<span class="attention-label">' + esc(r.attentionLabel) + '</span>';
    }
    if (r.status) {
      html += '<span class="sep">·</span>';
      html += '<span class="status">' + esc(r.status) + '</span>';
    }
    if (r.detail) {
      html += '<span class="detail">' + esc(r.detail) + '</span>';
    }
    html += '</div>';
    // Meta row
    var frozen = _frozenElapsed[ids[i]];
    var elapsed = frozen || (_startTimes[ids[i]] ? fmtElapsed(Date.now() - _startTimes[ids[i]]) : '');
    html += '<div class="meta">';
    if (r.contextPercent != null) {
      html += '<span id="ctx-' + ids[i] + '">' + r.contextPercent + '%</span>';
      html += '<span class="meta-sep">·</span>';
    }
    if (frozen) {
      html += '<span id="elapsed-' + ids[i] + '" style="font-weight:700">' + elapsed + '</span>';
    } else {
      html += '<span id="elapsed-' + ids[i] + '">' + elapsed + '</span>';
    }
    html += '</div>';
    html += '</div>';
  }
  pill.className = '';
  pill.innerHTML = html;
  requestResize();
}

function requestResize() {
  if (!window.glimpse) return;
  requestAnimationFrame(function() {
    var pill = document.getElementById('pill');
    var height = Math.ceil(pill.getBoundingClientRect().height + ${WINDOW_VERTICAL_PADDING});
    window.glimpse.send({ type: 'resize', height: height });
  });
}
</script>
</body>
</html>`;
}

// ── state ─────────────────────────────────────────────────────────────────────

const agents = new Map<string, AgentMessage>();
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

function pushUpdate(id: string, data: AgentMessage): void {
  const status = data.status ?? "";
  const color = STATUS_COLOR[status] ?? "#6B7280";
  const label = STATUS_LABEL[status] ?? "";
  const detail = truncate(data.detail ?? "", 60);
  const project = esc(data.project ?? "pi");
  const ctxPct = data.contextPercent ?? null;
  const attention = data.attention === true;
  const attentionLabel = data.attentionLabel ?? "";
  const js = `update(${JSON.stringify(id)},${JSON.stringify(color)},${JSON.stringify(project)},${JSON.stringify(label)},${JSON.stringify(detail)},${JSON.stringify(ctxPct)},${JSON.stringify(attention)},${JSON.stringify(attentionLabel)})`;
  if (winReady) win.send(js);
  else pendingUpdates.push(js);
}

function pushRemove(id: string): void {
  const js = `remove(${JSON.stringify(id)})`;
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
      const msg = JSON.parse(line) as AgentMessage;
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
