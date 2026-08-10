import type { ExtensionContext } from "@earendil-works/pi-coding-agent";

import { type BudgetCeiling, BudgetClient, type DailyCost } from "./budget-client.js";
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
    const [ceiling, days] = await Promise.all([
      client.getBudgetCeiling(force),
      client.getDailyCosts(force),
    ]);
    if (client !== this.client) return;

    if (!ceiling || !days) {
      ctx.ui.setStatus(BUDGET_STATUS_KEY, undefined);
      return;
    }

    const spent = days.reduce((sum, d) => sum + d.cost, 0);
    const percent = ceiling.budgetUsd > 0 ? (spent / ceiling.budgetUsd) * 100 : 0;

    const spentText = ctx.ui.theme.fg(colorForPercent(percent), `$${Math.round(spent)}`);
    const totalText =
      ceiling.budgetUsd > 0 ? ctx.ui.theme.fg("text", `/$${Math.round(ceiling.budgetUsd)}`) : "";
    const alert = projectionAlert(ctx, ceiling, days);
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
function projectionAlert(ctx: ExtensionContext, ceiling: BudgetCeiling, days: DailyCost[]): string {
  const eta = daysUntilExceed(days, ceiling.windowDays, ceiling.budgetUsd);
  if (eta === undefined) return "";
  const label = eta <= 0 ? "exceed now" : `exceed in ${eta}d`;
  return ` ${ctx.ui.theme.fg("error", `(\u26a0 ${label})`)}`;
}

function completeDays(days: DailyCost[]): DailyCost[] {
  const today = new Date().toISOString().slice(0, 10);
  return days.filter((d) => d.date !== today);
}

/** Mean daily spend over the most recent complete days — "last week's pace". */
function recentDailyRate(days: DailyCost[]): number | undefined {
  const recent = completeDays(days).slice(-RATE_WINDOW_DAYS);
  if (recent.length < 2) return undefined;
  return recent.reduce((sum, d) => sum + d.cost, 0) / recent.length;
}

/**
 * Days until the rolling-window spend first crosses the budget, projecting
 * forward at last week's rate: each simulated day adds the rate and drops the
 * oldest day out of the window. Returns undefined when the steady-state pace
 * stays within budget, 0 when already over it.
 */
function daysUntilExceed(
  days: DailyCost[],
  windowDays: number,
  budgetUsd: number,
): number | undefined {
  if (budgetUsd <= 0) return undefined;
  const rate = recentDailyRate(days);
  if (rate === undefined || rate * windowDays <= budgetUsd) return undefined;

  const window = completeDays(days)
    .slice(-windowDays)
    .map((d) => d.cost);
  let rollingSum = window.reduce((sum, c) => sum + c, 0);
  if (rollingSum > budgetUsd) return 0;

  for (let k = 1; k <= windowDays; k++) {
    const dropped = k <= window.length ? window[k - 1] : rate;
    rollingSum += rate - dropped;
    if (rollingSum > budgetUsd) return k;
  }
  return windowDays;
}
