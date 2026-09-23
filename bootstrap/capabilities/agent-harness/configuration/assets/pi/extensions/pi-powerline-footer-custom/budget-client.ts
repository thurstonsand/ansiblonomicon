import { mkdirSync, renameSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { getAgentDir } from "@earendil-works/pi-coding-agent";

import { isJsonObject, type JsonObject, readJsonFile } from "./json-file.js";

const CACHE_DIR = path.join(homedir(), ".cache", "claude-usage");
const BUDGET_CACHE_FILE = path.join(CACHE_DIR, "budget.json");
const DAILY_CACHE_FILE = path.join(CACHE_DIR, "daily-costs.json");

const CACHE_TTL_MS = 300_000; // both endpoints report spend, which changes continuously
const FETCH_TIMEOUT_MS = 5_000;

const DEFAULT_WINDOW_DAYS = 30;

export interface BudgetStatus {
  budgetUsd: number;
  windowDays: number;
  spentUsd: number;
  percentUsed: number;
}

/** One day's total spend across all services. */
export interface DailyCost {
  date: string;
  cost: number;
}

/**
 * Retrieves budget data, hiding the API calls, on-disk caching, and
 * parsing behind two typed getters. Each getter returns cached data, fetching
 * first only when the cache has gone stale (or when forced).
 */
export class BudgetClient {
  private readonly budgetEndpoint: string | undefined;
  private readonly costsEndpoint: string | undefined;
  private readonly inFlight = new Map<string, Promise<void>>();

  constructor(budgetEndpoint: string | undefined, costsEndpoint: string | undefined) {
    this.budgetEndpoint = budgetEndpoint;
    this.costsEndpoint = costsEndpoint;
  }

  async getBudgetStatus(force = false): Promise<BudgetStatus | undefined> {
    const endpoint = this.budgetEndpoint;
    if (!endpoint) return undefined;

    // Written in the full budgets-api shape so budget.json stays interchangeable
    // with the Claude statusline plugin's hook, which also owns this file.
    await this.ensureFresh(BUDGET_CACHE_FILE, force, async (token) => {
      const json = await fetchJson(endpoint, token);
      return isJsonObject(json) && parseBudgetStatus(json) ? json : undefined;
    });
    return readBudgetStatus();
  }

  async getDailyCosts(force = false): Promise<DailyCost[] | undefined> {
    const endpoint = this.costsEndpoint;
    if (!endpoint) return undefined;

    const windowDays = readBudgetStatus()?.windowDays ?? DEFAULT_WINDOW_DAYS;
    await this.ensureFresh(DAILY_CACHE_FILE, force, async (token) => {
      const days = await fetchDailyCosts(endpoint, token, windowDays);
      return days ? { days } : undefined;
    });
    return readDailyCosts();
  }

  /**
   * Fetch-and-write only when the cache is stale, deduplicating concurrent
   * callers so frequent footer renders never stack network calls.
   */
  private async ensureFresh(
    file: string,
    force: boolean,
    fetcher: (token: string) => Promise<JsonObject | undefined>,
  ): Promise<void> {
    if (!force && isFresh(file)) return;

    const pending = this.inFlight.get(file);
    if (pending) return pending;

    const task = (async () => {
      const token = readGatewayToken();
      if (!token) return;
      const data = await fetcher(token);
      if (data) writeCache(file, data);
    })().finally(() => {
      this.inFlight.delete(file);
    });
    this.inFlight.set(file, task);
    return task;
  }
}

/**
 * Every provider in models.json is the same gateway behind a different wire
 * protocol, sharing one token, so the first key found is the right one. Looking
 * one up by provider name would put the gateway's name in git.
 */
function readGatewayToken(): string | undefined {
  const models = readJsonFile(path.join(getAgentDir(), "models.json"));
  const providers = isJsonObject(models?.providers) ? models.providers : undefined;
  if (!providers) return undefined;

  for (const provider of Object.values(providers)) {
    if (isJsonObject(provider) && typeof provider.apiKey === "string") return provider.apiKey;
  }
  return undefined;
}

function readBudgetStatus(): BudgetStatus | undefined {
  const parsed = readJsonFile(BUDGET_CACHE_FILE);
  return parsed ? parseBudgetStatus(parsed) : undefined;
}

function parseBudgetStatus(parsed: JsonObject): BudgetStatus | undefined {
  const budgetUsd = numberOf(parsed.budget_usd);
  const spentUsd = numberOf(parsed.spent_usd);
  const percentUsed = numberOf(parsed.percent_used);
  if (budgetUsd === undefined || spentUsd === undefined || percentUsed === undefined) {
    return undefined;
  }

  return {
    budgetUsd,
    windowDays: numberOf(parsed.window_days) ?? DEFAULT_WINDOW_DAYS,
    spentUsd,
    percentUsed,
  };
}

function readDailyCosts(): DailyCost[] | undefined {
  const parsed = readJsonFile(DAILY_CACHE_FILE);
  if (!parsed || !Array.isArray(parsed.days)) return undefined;

  const days: DailyCost[] = [];
  for (const entry of parsed.days) {
    if (!isJsonObject(entry)) continue;
    const date = typeof entry.date === "string" ? entry.date : undefined;
    const cost = numberOf(entry.cost);
    if (date && cost !== undefined) days.push({ date, cost });
  }
  return days.length > 0 ? days : undefined;
}

function isFresh(file: string): boolean {
  try {
    return Date.now() - statSync(file).mtimeMs < CACHE_TTL_MS;
  } catch {
    return false;
  }
}

async function fetchDailyCosts(
  endpoint: string,
  token: string,
  windowDays: number,
): Promise<DailyCost[] | undefined> {
  const start = utcDateOffset(-windowDays);
  const end = utcDateOffset(1);
  const url = `${endpoint}?start=${start}&end=${end}`;

  const json = await fetchJson(url, token);
  if (!isJsonObject(json) || !Array.isArray(json.resources)) return undefined;

  const days: DailyCost[] = [];
  for (const entry of json.resources) {
    if (!isJsonObject(entry) || typeof entry.date !== "string") continue;
    const costs = Array.isArray(entry.costs) ? entry.costs : [];
    const total = costs.reduce<number>((sum, c) => {
      const cost = isJsonObject(c) ? numberOf(c.cost) : undefined;
      return sum + (cost ?? 0);
    }, 0);
    days.push({ date: entry.date, cost: total });
  }
  return days;
}

async function fetchJson(url: string, token: string): Promise<unknown> {
  try {
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    if (!response.ok) return undefined;

    const json: unknown = await response.json();
    if (isJsonObject(json) && "errors" in json) return undefined;
    return json;
  } catch {
    return undefined;
  }
}

function writeCache(file: string, data: JsonObject): void {
  try {
    mkdirSync(CACHE_DIR, { recursive: true });
    const tmpFile = `${file}.tmp.${process.pid}`;
    writeFileSync(tmpFile, JSON.stringify({ ...data, updatedAt: Date.now() }));
    renameSync(tmpFile, file);
  } catch {
    // Cache is best-effort; a failed write just defers the next refresh.
  }
}

function utcDateOffset(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function numberOf(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}
