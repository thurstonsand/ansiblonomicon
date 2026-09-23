import {
  type ExtensionContext,
  estimateTokens,
  sessionEntryToContextMessages,
} from "@earendil-works/pi-coding-agent";

export interface ContextUsage {
  tokens: number;
  contextWindow: number;
}

export class ContextUsageCache {
  private sessionManager: ExtensionContext["sessionManager"] | undefined;
  private leafId: string | null | undefined;
  private usage: ContextUsage | undefined;

  get(ctx: ExtensionContext): ContextUsage | undefined {
    const sessionManager = ctx.sessionManager;
    const leafId = sessionManager.getLeafId();
    if (this.sessionManager !== sessionManager || this.leafId !== leafId) {
      this.sessionManager = sessionManager;
      this.leafId = leafId;
      this.usage = readKnownContextUsage(ctx);
    }
    return this.usage;
  }

  reset(): void {
    this.sessionManager = undefined;
    this.leafId = undefined;
    this.usage = undefined;
  }
}

export function estimateUnknownContextUsage(ctx: ExtensionContext): ContextUsage | undefined {
  const usage = ctx.getContextUsage();
  if (!usage || usage.tokens !== null) return undefined;

  const messageTokens = ctx.sessionManager
    .buildContextEntries()
    .flatMap(sessionEntryToContextMessages)
    .reduce((total, message) => total + estimateTokens(message), 0);
  const systemPrompt = ctx.getSystemPrompt();
  const systemPromptTokens = systemPrompt.trim() ? Math.ceil(systemPrompt.length / 4) : 0;

  return {
    tokens: systemPromptTokens + messageTokens,
    contextWindow: usage.contextWindow,
  };
}

function readKnownContextUsage(ctx: ExtensionContext): ContextUsage | undefined {
  const usage = ctx.getContextUsage();
  if (!usage || usage.tokens === null) return undefined;
  return { tokens: usage.tokens, contextWindow: usage.contextWindow };
}
