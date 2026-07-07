// @ts-check

/**
 * @typedef {Object} CompanionTheme
 * @property {string} pillBg
 * @property {string} border
 * @property {string} shadow
 * @property {string} divider
 * @property {string} text
 * @property {string} muted
 * @property {string} subtle
 * @property {string} separator
 * @property {string} attentionDot
 * @property {string} attentionGlow
 * @property {string} attentionPulse
 * @property {Record<string, string>} dots
 */

/**
 * @typedef {Object} CompanionConfig
 * @property {number} maxVisibleSessions
 * @property {string} fontFamily
 */

/**
 * @typedef {Object} SessionUpdate
 * @property {string} id
 * @property {string | undefined} project
 * @property {string | undefined} status
 * @property {string | undefined} detail
 * @property {number | undefined} contextPercent
 * @property {boolean | undefined} attention
 * @property {string | undefined} attentionLabel
 * @property {CompanionTheme | undefined} theme
 */

/**
 * @typedef {Object} SessionRecord
 * @property {string} id
 * @property {string} project
 * @property {string} status
 * @property {string} detail
 * @property {number | null} contextPercent
 * @property {boolean} attention
 * @property {string} attentionLabel
 * @property {number} sequence
 * @property {number} firstSeen
 * @property {number} startedAt
 * @property {number | null} attentionStarted
 * @property {string | null} frozenElapsed
 */

/**
 * @typedef {Object} OverflowView
 * @property {number} hiddenAttentionCount
 * @property {number} hiddenNormalCount
 * @property {string} dotColor
 * @property {boolean} attention
 * @property {string} text
 */

/**
 * @typedef {Object} CompanionView
 * @property {CompanionTheme} theme
 * @property {SessionRecord[]} rows
 * @property {OverflowView | null} overflow
 */

/**
 * @typedef {Object} EntryElements
 * @property {HTMLDivElement} root
 * @property {HTMLDivElement} row
 * @property {HTMLDivElement} dot
 * @property {HTMLSpanElement} project
 * @property {HTMLSpanElement} statusSep
 * @property {HTMLSpanElement} status
 * @property {HTMLSpanElement} detail
 * @property {HTMLSpanElement} context
 * @property {HTMLSpanElement} metaSep
 * @property {HTMLSpanElement} elapsed
 */

/**
 * @typedef {Object} OverflowElements
 * @property {HTMLDivElement} root
 * @property {HTMLDivElement} dot
 * @property {HTMLSpanElement} text
 */

/** @type {Window & { __COMPANION_CONFIG__?: CompanionConfig, Companion?: unknown, glimpse?: { send: (data: unknown) => void } }} */
const companionWindow = window;

/** @type {CompanionTheme} */
const DEFAULT_THEME = {
  pillBg: "rgba(29,32,33,0.92)",
  border: "#504945",
  shadow: "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)",
  divider: "rgba(235,219,178,0.055)",
  text: "rgba(255,255,255,0.95)",
  muted: "rgba(255,255,255,0.9)",
  subtle: "rgba(255,255,255,0.75)",
  separator: "rgba(255,255,255,0.5)",
  attentionDot: "#c084fc",
  attentionGlow: "#ff2fa3",
  attentionPulse: "rgba(255,255,255,0.13)",
  dots: {
    starting: "#bdae93",
    thinking: "#928374",
    responding: "#ebdbb2",
    preparing_tool: "#928374",
    reading: "#8ec07c",
    editing: "#fabd2f",
    running: "#fe8019",
    searching: "#83a598",
    compacting: "#928374",
    done: "#b8bb26",
    error: "#fb4934",
  },
};

/** @type {Record<string, string>} */
const STATUS_LABEL = {
  starting: "Starting",
  thinking: "Thinking",
  responding: "Responding",
  preparing_tool: "Preparing tool",
  reading: "Reading",
  editing: "Editing",
  running: "Running",
  searching: "Searching",
  compacting: "Compacting",
  done: "Done",
  error: "Error",
};

const WINDOW_VERTICAL_PADDING = 72;
const FALLBACK_FONT_STACK = "Menlo, Monaco, ui-monospace, 'SF Mono', monospace";

const rawConfig = companionWindow.__COMPANION_CONFIG__;
if (!rawConfig) throw new Error("Missing companion config");
/** @type {CompanionConfig} */
const config = rawConfig;

/** @type {Map<string, SessionRecord>} */
const sessions = new Map();
/** @type {Map<string, EntryElements>} */
const entries = new Map();
/** @type {OverflowElements | null} */
let overflowElements = null;
/** @type {ReturnType<typeof setInterval> | null} */
let tickTimer = null;
let sequence = 0;
let currentThemeKey = "";
let theme = DEFAULT_THEME;

document.body.style.setProperty(
  "--companion-font-stack",
  `${JSON.stringify(config.fontFamily)}, ${FALLBACK_FONT_STACK}`,
);

/** @param {number} ms */
function fmtElapsed(ms) {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}m ${rem < 10 ? "0" : ""}${rem}s`;
}

/** @param {string} s @param {number} max */
function truncate(s, max) {
  if (!s) return "";
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

/** @param {string} status */
function statusLabel(status) {
  return STATUS_LABEL[status] ?? status;
}

/** @param {SessionRecord} record */
function statusDotColor(record) {
  return theme.dots[record.status] ?? theme.dots.running ?? "#6b7280";
}

function startTick() {
  if (tickTimer) return;
  tickTimer = setInterval(() => {
    if (sessions.size === 0) {
      if (tickTimer) clearInterval(tickTimer);
      tickTimer = null;
      return;
    }
    for (const record of sessions.values()) {
      if (record.frozenElapsed) continue;
      const entry = entries.get(record.id);
      if (entry) entry.elapsed.textContent = fmtElapsed(Date.now() - record.startedAt);
    }
  }, 1000);
}

/** @param {SessionUpdate} update */
function updateSession(update) {
  const now = Date.now();
  const previous = sessions.get(update.id);
  const startedAt = previous?.startedAt ?? now;
  const frozenElapsed =
    previous?.frozenElapsed ?? (update.status === "Done" ? fmtElapsed(now - startedAt) : null);
  const attentionStarted = update.attention ? (previous?.attentionStarted ?? now) : null;

  theme = update.theme ?? theme;
  sessions.set(update.id, {
    id: update.id,
    project: update.project ?? "pi",
    status: update.status ?? "",
    detail: truncate(update.detail ?? "", 60),
    contextPercent: update.contextPercent ?? null,
    attention: update.attention === true,
    attentionLabel: update.attentionLabel ?? "",
    sequence: ++sequence,
    firstSeen: previous?.firstSeen ?? now,
    startedAt,
    attentionStarted,
    frozenElapsed,
  });
  reconcile(declareView());
  startTick();
}

/** @param {string} id */
function removeSession(id) {
  sessions.delete(id);
  const entry = entries.get(id);
  if (entry) entry.root.remove();
  entries.delete(id);
  reconcile(declareView());
}

/** @returns {CompanionView} */
function declareView() {
  const records = Array.from(sessions.values());
  const attentionRows = records.filter((record) => record.attention).sort(compareAttentionRows);
  const normalRows = records.filter((record) => !record.attention).sort(compareFirstSeen);
  const orderedRows = attentionRows.concat(normalRows);
  const visibleRows = orderedRows.slice(0, config.maxVisibleSessions);
  const hiddenRows = orderedRows.slice(config.maxVisibleSessions);

  return {
    theme,
    rows: visibleRows,
    overflow: declareOverflow(hiddenRows),
  };
}

/** @param {SessionRecord[]} hiddenRows @returns {OverflowView | null} */
function declareOverflow(hiddenRows) {
  if (hiddenRows.length === 0) return null;
  const hiddenAttentionCount = hiddenRows.filter((record) => record.attention).length;
  const hiddenNormalCount = hiddenRows.length - hiddenAttentionCount;
  const latestHidden = hiddenRows.reduce(
    (latest, record) => (!latest || record.sequence > latest.sequence ? record : latest),
    /** @type {SessionRecord | null} */ (null),
  );
  const parts = [];
  if (hiddenAttentionCount > 0) parts.push(`+${hiddenAttentionCount} need attention`);
  if (hiddenNormalCount > 0) parts.push(`+${hiddenNormalCount} active`);

  return {
    hiddenAttentionCount,
    hiddenNormalCount,
    dotColor:
      hiddenAttentionCount > 0
        ? "var(--attention-dot, #c084fc)"
        : latestHidden
          ? statusDotColor(latestHidden)
          : "var(--pill-subtle, rgba(255,255,255,0.75))",
    attention: hiddenAttentionCount > 0,
    text: parts.join(" · "),
  };
}

/** @param {SessionRecord} a @param {SessionRecord} b */
function compareAttentionRows(a, b) {
  return (
    (a.attentionStarted ?? a.firstSeen) - (b.attentionStarted ?? b.firstSeen) ||
    compareFirstSeen(a, b)
  );
}

/** @param {SessionRecord} a @param {SessionRecord} b */
function compareFirstSeen(a, b) {
  return a.firstSeen - b.firstSeen;
}

/** @param {CompanionView} view */
function reconcile(view) {
  const pill = getPill();
  if (sessions.size === 0) {
    pill.style.opacity = "0";
    setTimeout(() => {
      if (sessions.size !== 0) return;
      pill.replaceChildren();
      entries.clear();
      overflowElements = null;
    }, 350);
    requestResize();
    return;
  }

  pill.style.opacity = "1";
  reconcileTheme(pill, view.theme);
  reconcileRows(pill, view.rows);
  reconcileOverflow(pill, view.overflow, view.rows.length);
  requestResize();
}

/** @param {HTMLElement} root @param {CompanionTheme} nextTheme */
function reconcileTheme(root, nextTheme) {
  const nextThemeKey = JSON.stringify(nextTheme);
  if (nextThemeKey === currentThemeKey) return;
  currentThemeKey = nextThemeKey;
  setThemeVars(root, nextTheme);
}

/** @param {HTMLElement} pill @param {SessionRecord[]} rows */
function reconcileRows(pill, rows) {
  const visibleIds = new Set(rows.map((record) => record.id));
  for (const [id, entry] of entries) {
    if (!visibleIds.has(id)) {
      entry.root.remove();
      entries.delete(id);
    }
  }

  rows.forEach((record, index) => {
    const entry = ensureEntry(record.id);
    updateEntry(entry, record);
    placeChild(pill, entry.root, index);
  });
}

/** @param {HTMLElement} pill @param {OverflowView | null} overflow @param {number} index */
function reconcileOverflow(pill, overflow, index) {
  if (!overflow) {
    overflowElements?.root.remove();
    overflowElements = null;
    return;
  }

  const elements = ensureOverflow();
  elements.root.className = overflow.attention ? "overflow-row attention" : "overflow-row";
  elements.dot.style.background = overflow.dotColor;
  elements.text.textContent = overflow.text;
  placeChild(pill, elements.root, index);
}

/** @param {string} id */
function ensureEntry(id) {
  const existing = entries.get(id);
  if (existing) return existing;
  const created = createEntry(id);
  entries.set(id, created);
  return created;
}

/** @param {string} id @returns {EntryElements} */
function createEntry(id) {
  const root = document.createElement("div");
  root.id = `r-${id}`;
  root.className = "entry";

  const row = document.createElement("div");
  row.className = "row";
  const dot = document.createElement("div");
  dot.className = "dot";
  const project = createText("project");
  const statusSep = createText("sep status-sep");
  const status = createText("status");
  const detail = createText("detail");
  row.append(dot, project, statusSep, status, detail);

  const meta = document.createElement("div");
  meta.className = "meta";
  const context = createText("context");
  const metaSep = createText("meta-sep");
  const elapsed = createText("elapsed");
  meta.append(context, metaSep, elapsed);

  root.append(row, meta);
  return {
    root,
    row,
    dot,
    project,
    statusSep,
    status,
    detail,
    context,
    metaSep,
    elapsed,
  };
}

/** @param {EntryElements} entry @param {SessionRecord} record */
function updateEntry(entry, record) {
  entry.root.className = record.attention ? "entry attention" : "entry";
  entry.row.className = record.attention ? "row attention" : "row";
  const label = record.attentionLabel || statusLabel(record.status);
  entry.dot.style.background = record.attention
    ? "var(--attention-dot, #c084fc)"
    : statusDotColor(record);
  setText(entry.project, record.project);
  setText(entry.statusSep, label ? "·" : "");
  setText(entry.status, label);
  entry.status.style.color = record.attention ? "var(--attention-dot, #c084fc)" : "";
  setText(entry.detail, record.detail);

  entry.context.id = `ctx-${record.id}`;
  entry.elapsed.id = `elapsed-${record.id}`;
  setText(entry.context, record.contextPercent != null ? `${record.contextPercent}%` : "");
  setText(entry.metaSep, record.contextPercent != null ? "·" : "");
  setText(entry.elapsed, record.frozenElapsed ?? fmtElapsed(Date.now() - record.startedAt));
  entry.elapsed.style.fontWeight = record.frozenElapsed ? "700" : "";
}

/** @returns {OverflowElements} */
function ensureOverflow() {
  if (overflowElements) return overflowElements;
  const root = document.createElement("div");
  root.id = "overflow-row";
  root.className = "overflow-row";
  const dot = document.createElement("div");
  dot.className = "dot";
  const text = createText("overflow-text");
  root.append(dot, text);
  overflowElements = { root, dot, text };
  return overflowElements;
}

/** @param {string} className */
function createText(className) {
  const el = document.createElement("span");
  el.className = className;
  return el;
}

/** @param {HTMLElement} el @param {string | number | null | undefined} value */
function setText(el, value) {
  const text = value == null ? "" : String(value);
  el.textContent = text;
  el.style.display = text ? "" : "none";
}

/** @param {HTMLElement} parent @param {Element} child @param {number} index */
function placeChild(parent, child, index) {
  if (parent.children[index] !== child) parent.insertBefore(child, parent.children[index] || null);
}

/** @param {HTMLElement} el @param {CompanionTheme} nextTheme */
function setThemeVars(el, nextTheme) {
  const t = nextTheme || DEFAULT_THEME;
  el.style.setProperty("--pill-bg", t.pillBg || DEFAULT_THEME.pillBg);
  el.style.setProperty("--pill-border", t.border || DEFAULT_THEME.border);
  el.style.setProperty("--pill-shadow", t.shadow || DEFAULT_THEME.shadow);
  el.style.setProperty("--pill-divider", t.divider || DEFAULT_THEME.divider);
  el.style.setProperty("--pill-text", t.text || DEFAULT_THEME.text);
  el.style.setProperty("--pill-muted", t.muted || DEFAULT_THEME.muted);
  el.style.setProperty("--pill-subtle", t.subtle || DEFAULT_THEME.subtle);
  el.style.setProperty("--pill-separator", t.separator || DEFAULT_THEME.separator);
  el.style.setProperty("--attention-dot", t.attentionDot || DEFAULT_THEME.attentionDot);
  el.style.setProperty("--attention-glow", t.attentionGlow || DEFAULT_THEME.attentionGlow);
  el.style.setProperty("--attention-pulse", t.attentionPulse || DEFAULT_THEME.attentionPulse);
}

function requestResize() {
  if (!companionWindow.glimpse) return;
  requestAnimationFrame(() => {
    companionWindow.glimpse?.send({
      type: "resize",
      height: Math.ceil(getPill().scrollHeight + WINDOW_VERTICAL_PADDING),
    });
  });
}

/** @returns {HTMLElement} */
function getPill() {
  const pill = document.getElementById("pill");
  if (!pill) throw new Error("Missing companion pill");
  return pill;
}

companionWindow.Companion = {
  update: updateSession,
  remove: removeSession,
};
