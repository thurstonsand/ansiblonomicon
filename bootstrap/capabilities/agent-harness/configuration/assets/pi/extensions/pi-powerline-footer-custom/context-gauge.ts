import {
  calculateContextTokens,
  type ExtensionContext,
  type MessageUpdateEvent,
  type SessionStartEvent,
} from "@earendil-works/pi-coding-agent";

import {
  type ContextUsage,
  ContextUsageCache,
  estimateUnknownContextUsage,
} from "./context-usage.js";
import { DebouncedTask } from "./debounced-task.js";
import { colorForPercent, renderGauge } from "./gauge.js";
import { getCompactionReserveTokens } from "./settings.js";

const STATUS_KEY = "context_gauge";
const SOFT_MAX_TOKENS = 400_000;
const STATUS_UPDATE_MS = 250;

interface ContextGauge {
  percent: number;
  overSoftMax: boolean;
}

interface ContextGaugeUpdate {
  ctx: ExtensionContext;
  liveTokens?: number;
}

export class ContextGaugeStatus {
  private reserveTokens: number | undefined;
  private readonly usageCache = new ContextUsageCache();
  private approximateUsage: ContextUsage | undefined;
  private readonly updateTask = new DebouncedTask<ContextGaugeUpdate>(
    STATUS_UPDATE_MS,
    ({ ctx, liveTokens }) => this.update(ctx, liveTokens),
  );

  sessionStart(event: SessionStartEvent, ctx: ExtensionContext): void {
    this.updateTask.reset();
    this.reserveTokens = getCompactionReserveTokens(ctx.cwd);
    this.usageCache.reset();
    this.approximateUsage =
      event.reason === "reload" ? estimateUnknownContextUsage(ctx) : undefined;
    this.update(ctx);
  }

  modelSelect(ctx: ExtensionContext): void {
    this.refresh(ctx);
  }

  sessionTree(ctx: ExtensionContext): void {
    this.updateTask.reset();
    this.refresh(ctx);
  }

  messageUpdate(event: MessageUpdateEvent, ctx: ExtensionContext): void {
    const message = event.message;
    if (
      message.role !== "assistant" ||
      message.stopReason === "error" ||
      message.stopReason === "aborted"
    ) {
      return;
    }

    const tokens = calculateContextTokens(message.usage);
    if (tokens > 0) this.updateTask.schedule({ ctx, liveTokens: tokens });
  }

  messageEnd(ctx: ExtensionContext): void {
    this.updateTask.flush({ ctx });
  }

  sessionBeforeCompact(ctx: ExtensionContext): void {
    this.updateTask.reset();
    this.clear(ctx);
  }

  sessionCompact(ctx: ExtensionContext): void {
    this.showCurrentUsage(ctx);
  }

  agentSettled(ctx: ExtensionContext): void {
    this.updateTask.flush({ ctx });
  }

  sessionShutdown(): void {
    this.updateTask.reset();
    this.reserveTokens = undefined;
    this.usageCache.reset();
    this.approximateUsage = undefined;
  }

  refresh(ctx: ExtensionContext): void {
    this.updateTask.reset();
    this.showCurrentUsage(ctx);
  }

  private showCurrentUsage(ctx: ExtensionContext): void {
    this.usageCache.reset();
    this.approximateUsage = estimateUnknownContextUsage(ctx);
    this.update(ctx);
  }

  private update(ctx: ExtensionContext, liveTokens?: number): void {
    if (liveTokens !== undefined) this.usageCache.reset();
    const usage =
      liveTokens === undefined ? this.usageCache.get(ctx) : this.liveUsage(ctx, liveTokens);
    const approximate = usage === undefined && this.approximateUsage !== undefined;
    const displayUsage = usage ?? this.approximateUsage;
    if (!displayUsage) {
      ctx.ui.setStatus(STATUS_KEY, undefined);
      return;
    }

    if (usage) this.approximateUsage = undefined;
    this.render(ctx, displayUsage, approximate);
  }

  private clear(ctx: ExtensionContext): void {
    this.usageCache.reset();
    this.approximateUsage = undefined;
    ctx.ui.setStatus(STATUS_KEY, undefined);
  }

  private liveUsage(ctx: ExtensionContext, tokens: number): ContextUsage | undefined {
    const contextWindow = ctx.model?.contextWindow;
    return contextWindow ? { tokens, contextWindow } : undefined;
  }

  private render(ctx: ExtensionContext, usage: ContextUsage, approximate: boolean): void {
    const gauge = calculateContextGauge(
      usage.tokens,
      usage.contextWindow,
      this.requireReserveTokens(),
    );
    ctx.ui.setStatus(
      STATUS_KEY,
      ctx.ui.theme.fg(
        colorForPercent(gauge.percent, gauge.overSoftMax),
        renderGauge(gauge.percent, gauge.overSoftMax, approximate),
      ),
    );
  }

  private requireReserveTokens(): number {
    if (this.reserveTokens === undefined) {
      throw new Error("Context gauge has not started");
    }
    return this.reserveTokens;
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
