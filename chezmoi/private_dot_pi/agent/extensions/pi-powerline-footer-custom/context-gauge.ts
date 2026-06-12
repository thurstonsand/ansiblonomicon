import type { ExtensionContext } from "@earendil-works/pi-coding-agent";

import { colorForPercent, renderGauge } from "./gauge.js";
import { getCompactionReserveTokens } from "./settings.js";

const STATUS_KEY = "context_gauge";
const SOFT_MAX_TOKENS = 400_000;

interface ContextGauge {
  percent: number;
  overSoftMax: boolean;
}

export class ContextGaugeStatus {
  private readonly cwd: string;

  constructor(cwd: string) {
    this.cwd = cwd;
  }

  update(ctx: ExtensionContext): void {
    const usage = ctx.getContextUsage();
    if (!usage || usage.tokens === null) return;

    const gauge = calculateContextGauge(
      usage.tokens,
      usage.contextWindow,
      getCompactionReserveTokens(this.cwd),
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
): ContextGauge {
  const compactionThreshold = contextWindow - reserveTokens;
  const softMax = Math.min(compactionThreshold, SOFT_MAX_TOKENS);
  const overSoftMax = compactionThreshold > softMax && tokens > softMax;
  const denominator = overSoftMax ? compactionThreshold : softMax;
  const percent = (tokens / denominator) * 100;

  return { percent, overSoftMax };
}
