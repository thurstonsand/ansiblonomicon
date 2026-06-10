import { mkdirSync, renameSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { type ExtensionContext, getAgentDir, SettingsManager } from "@earendil-works/pi-coding-agent";

import { colorForPercent } from "./gauge.js";
import { isJsonObject, type JsonObject, readJsonFile } from "./json-file.js";

const STATUS_KEY = "cost_budget";
const CACHE_DIR = path.join(homedir(), ".cache", "claude-usage");
const CACHE_FILE = path.join(CACHE_DIR, "budget.json");
const REFRESH_TTL_MS = 300_000;
const FETCH_TIMEOUT_MS = 5_000;

interface Budget {
  spentUsd: number;
  budgetUsd: number;
  percentUsed: number;
}

interface InferenceBudgetSettings {
  readonly url: string | undefined;
}

interface PiSettings {
  readonly inferenceBudget: InferenceBudgetSettings;
}

export class CostBudgetStatus {
  private readonly endpoint: string | undefined;
  private refreshing = false;

  constructor() {
    this.endpoint = loadSettings().inferenceBudget.url;
  }

  update(ctx: ExtensionContext): void {
    const budget = this.endpoint ? readBudget() : undefined;
    if (!budget) {
      ctx.ui.setStatus(STATUS_KEY, undefined);
      return;
    }

    const spent = ctx.ui.theme.fg(
      colorForPercent(budget.percentUsed),
      `$${Math.round(budget.spentUsd)}`,
    );
    const total = budget.budgetUsd > 0 ? ctx.ui.theme.fg("text", `/$${Math.round(budget.budgetUsd)}`) : "";
    ctx.ui.setStatus(STATUS_KEY, `${spent}${total}`);
  }

  async refresh(ctx: ExtensionContext, force = false): Promise<void> {
    if (!this.endpoint || this.refreshing || (!force && isCacheFresh())) return;
    this.refreshing = true;
    try {
      const token = readAnthropicToken();
      if (!token) return;

      const data = await fetchBudget(this.endpoint, token);
      if (!data) return;

      writeCache(data);
      this.update(ctx);
    } finally {
      this.refreshing = false;
    }
  }
}

function loadSettings(): PiSettings {
  const raw = SettingsManager.create(process.cwd()).getGlobalSettings() as Record<string, unknown>;
  const inferenceBudget = isJsonObject(raw.inferenceBudget) ? raw.inferenceBudget : undefined;
  const url = typeof inferenceBudget?.url === "string" && inferenceBudget.url.length > 0
    ? inferenceBudget.url
    : undefined;
  return { inferenceBudget: { url } };
}

function readAnthropicToken(): string | undefined {
  const auth = readJsonFile(path.join(getAgentDir(), "auth.json"));
  const anthropic = isJsonObject(auth?.anthropic) ? auth.anthropic : undefined;
  return typeof anthropic?.key === "string" ? anthropic.key : undefined;
}

function readBudget(): Budget | undefined {
  const parsed = readJsonFile(CACHE_FILE);
  if (!parsed) return undefined;

  const spentUsd = numberOf(parsed.spent_usd);
  const percentUsed = numberOf(parsed.percent_used);
  if (spentUsd === undefined || percentUsed === undefined) return undefined;

  return { spentUsd, budgetUsd: numberOf(parsed.budget_usd) ?? 0, percentUsed };
}

function isCacheFresh(): boolean {
  try {
    return Date.now() - statSync(CACHE_FILE).mtimeMs < REFRESH_TTL_MS;
  } catch {
    return false;
  }
}

async function fetchBudget(endpoint: string, token: string): Promise<JsonObject | undefined> {
  try {
    const response = await fetch(endpoint, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    if (!response.ok) return undefined;

    const json: unknown = await response.json();
    if (!isJsonObject(json) || "errors" in json) return undefined;
    if (typeof json.spent_usd !== "number") return undefined;

    return json;
  } catch {
    return undefined;
  }
}

function writeCache(data: JsonObject): void {
  try {
    mkdirSync(CACHE_DIR, { recursive: true });
    const tmpFile = `${CACHE_FILE}.tmp.${process.pid}`;
    writeFileSync(tmpFile, JSON.stringify({ ...data, updatedAt: Date.now() }));
    renameSync(tmpFile, CACHE_FILE);
  } catch {
    // Cache is best-effort; a failed write just defers the next refresh.
  }
}

function numberOf(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}
