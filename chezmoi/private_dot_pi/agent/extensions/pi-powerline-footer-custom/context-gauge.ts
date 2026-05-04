import { type ExtensionContext, getAgentDir, SettingsManager } from "@mariozechner/pi-coding-agent";

import { colorForPercent, renderGauge } from "./gauge.js";

const STATUS_KEY = "context_gauge";
const SOFT_MAX_TOKENS = 400_000;

export class ContextGaugeStatus {
  private readonly settingsManager: SettingsManager;

  constructor(cwd: string) {
    this.settingsManager = SettingsManager.create(cwd, getAgentDir());
  }

  update(ctx: ExtensionContext): void {
    const usage = ctx.getContextUsage();
    if (!usage || usage.contextWindow <= 0 || usage.tokens === null) {
      ctx.ui.setStatus(STATUS_KEY, undefined);
      return;
    }

    const gauge = calculateContextGauge(
      usage.tokens,
      usage.contextWindow,
      this.settingsManager.getCompactionReserveTokens(),
    );

    ctx.ui.setStatus(
      STATUS_KEY,
      ctx.ui.theme.fg(
        colorForPercent(gauge.percent, gauge.overSoftMax),
        renderGauge(gauge.percent, gauge.overSoftMax),
      ),
    );
  }
}

export function calculateContextGauge(
  tokens: number,
  contextWindow: number,
  reserveTokens: number,
): { percent: number; overSoftMax: boolean } {
  const compactionTokens = Math.max(1, contextWindow - reserveTokens);
  const softMax = Math.min(compactionTokens, SOFT_MAX_TOKENS);
  const overSoftMax = compactionTokens > softMax && tokens > softMax;
  const percent = (tokens / (overSoftMax ? compactionTokens : softMax)) * 100;

  return { percent, overSoftMax };
}
