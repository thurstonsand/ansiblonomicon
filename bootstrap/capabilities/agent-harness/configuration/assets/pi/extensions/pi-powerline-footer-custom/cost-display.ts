import type { ExtensionContext } from "@earendil-works/pi-coding-agent";

import { BudgetClient, type BudgetStatus, type DailyCost } from "./budget-client.js";
import { colorForPercent } from "./gauge.js";
import { getBudgetSettings } from "./settings.js";

const BUDGET_STATUS_KEY = "cost_budget";
const RATE_WINDOW_DAYS = 7; // "at last week's pace"

export class CostBudgetStatus {
  private client: BudgetClient | undefined;

  sessionStart(ctx: ExtensionContext): void {
    const budget = getBudgetSettings();
    this.client = new BudgetClient(budget.url, budget.costsUrl);
    void this.refresh(ctx);
  }

  turnEnd(ctx: ExtensionContext): void {
    void this.refresh(ctx);
  }

  sessionShutdown(): void {
    this.client = undefined;
  }

  async refresh(ctx: ExtensionContext, force = false): Promise<void> {
    const client = this.requireClient();
    const [status, days] = await Promise.all([
      client.getBudgetStatus(force),
      client.getDailyCosts(force),
    ]);
    if (client !== this.client) return;

    if (!status || !days) {
      ctx.ui.setStatus(BUDGET_STATUS_KEY, undefined);
      return;
    }

    const spentText = ctx.ui.theme.fg(
      colorForPercent(status.percentUsed),
      `$${Math.round(status.spentUsd)}`,
    );
    const totalText =
      status.budgetUsd > 0 ? ctx.ui.theme.fg("text", `/$${Math.round(status.budgetUsd)}`) : "";
    const alert = projectionAlert(ctx, status, days);
    ctx.ui.setStatus(BUDGET_STATUS_KEY, `${spentText}${alert}${totalText}`);
  }

  private requireClient(): BudgetClient {
    if (!this.client) throw new Error("Cost budget status has not started");
    return this.client;
  }
}

/**
 * Inline overshoot warning: rendered only when last week's pace projects past
 * the budget. Empty otherwise.
 */
function projectionAlert(ctx: ExtensionContext, status: BudgetStatus, days: DailyCost[]): string {
  const eta = daysUntilExceed(days, status);
  if (eta === undefined) return "";
  const label = eta <= 0 ? "exceed now" : `exceed in ${eta}d`;
  return ` ${ctx.ui.theme.fg("error", `(\u26a0 ${label})`)}`;
}

function completeDays(days: DailyCost[]): DailyCost[] {
  const today = new Date().toISOString().slice(0, 10);
  return days.filter((d) => d.date !== today);
}

/**
 * The ledger days a reset cannot have touched. Resets carry no date, but one
 * must lie within the oldest day whose running suffix reaches reported spend,
 * so that day mixes pre- and post-reset cost and goes out with the rest of the
 * history behind it. Empty when the ledger cannot account for reported spend at
 * all, which keeps a disagreement between the two services silent.
 */
function postResetDays(days: DailyCost[], spentUsd: number): DailyCost[] {
  let suffix = 0;
  for (let i = days.length - 1; i >= 0; i--) {
    suffix += days[i].cost;
    if (suffix >= spentUsd) return days.slice(i + 1);
  }
  return [];
}

/** Mean daily spend over the most recent complete days — "last week's pace". */
function recentDailyRate(history: DailyCost[]): number | undefined {
  const recent = history.slice(-RATE_WINDOW_DAYS);
  if (recent.length < 2) return undefined;
  return recent.reduce((sum, d) => sum + d.cost, 0) / recent.length;
}

/**
 * Days until the rolling-window spend first crosses the budget, projecting
 * forward at last week's rate from the gateway's reported spend. Each simulated
 * day adds the rate and drops whatever leaves the window; after a reset the
 * window is only partly filled, so the empty slots leave first and nothing rolls
 * off until real days reach the far edge. Returns undefined when the pace stays
 * within budget or there is too little post-reset history to read a pace from,
 * 0 when already over.
 */
function daysUntilExceed(days: DailyCost[], status: BudgetStatus): number | undefined {
  const { budgetUsd, windowDays, spentUsd } = status;
  if (budgetUsd <= 0) return undefined;
  if (spentUsd > budgetUsd) return 0;

  const history = completeDays(postResetDays(days, spentUsd));
  const rate = recentDailyRate(history);
  if (rate === undefined || rate * windowDays <= budgetUsd) return undefined;

  const window = history.slice(-windowDays).map((d) => d.cost);
  const emptySlots = windowDays - window.length;
  let rollingSum = spentUsd;

  for (let k = 1; k <= windowDays; k++) {
    const dropped = k <= emptySlots ? 0 : window[k - emptySlots - 1];
    rollingSum += rate - dropped;
    if (rollingSum > budgetUsd) return k;
  }
  return windowDays;
}
