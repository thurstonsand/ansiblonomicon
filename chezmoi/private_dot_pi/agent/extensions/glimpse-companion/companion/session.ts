import { randomUUID } from "node:crypto";
import { basename } from "node:path";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import { AttentionTracker, parseAttentionRequest, parseAttentionResolve } from "./attention.js";
import { CompanionConnection } from "./connection.js";
import {
  type FollowCursorSupport,
  loadFollowCursorSupport,
  resolveNode,
} from "./glimpse-support.js";
import { loadEnabled } from "./settings.js";
import { COMPANION_STATUS, type CompanionStatus, statusForTool } from "./status.js";

const SESSION_ID = randomUUID().slice(0, 8);

interface CompanionMessage {
  id: string;
  project: string;
  status: string;
  detail?: string;
  contextPercent?: number;
}

/**
 * Owns the mutable per-session companion state and translates pi activity into
 * socket messages. Event registration lives in handlers.ts / command.ts; this
 * class exposes the intent-level operations they call.
 */
export class CompanionSession {
  private enabled = loadEnabled();
  private lastStatus: CompanionStatus | "" = "";
  private lastCtx: ExtensionContext | null = null;
  private warnedUnsupported = false;
  private followCursorSupport: FollowCursorSupport = { supported: true };
  private glimpseLoaded = false;
  private readonly project = basename(process.cwd());
  private readonly connection = new CompanionConnection();
  private readonly attention = new AttentionTracker<CompanionStatus | "">();

  get isEnabled(): boolean {
    return this.enabled;
  }

  get isSupported(): boolean {
    return this.followCursorSupport.supported;
  }

  private get active(): boolean {
    return this.enabled && this.followCursorSupport.supported;
  }

  noteContext(ctx: ExtensionContext): void {
    this.lastCtx = ctx;
  }

  async enable(ctx: ExtensionContext): Promise<void> {
    this.enabled = true;
    await this.loadGlimpse();
    if (!this.followCursorSupport.supported) {
      this.maybeNotifyUnsupported(ctx);
      ctx.ui.setStatus("companion", undefined);
      return;
    }
    await this.connection.ensureConnected();
    if (!this.connection.isConnected && !resolveNode()) {
      ctx.ui.notify(
        "Companion needs a node interpreter on PATH (set GLIMPSE_NODE to override)",
        "info",
      );
    }
    const theme = ctx.ui.theme;
    ctx.ui.setStatus("companion", theme.fg("accent", "G") + theme.fg("dim", " ·"));
  }

  disable(ctx: ExtensionContext): void {
    this.enabled = false;
    this.teardown();
    ctx.ui.setStatus("companion", undefined);
  }

  // ── activity ───────────────────────────────────────────────────────────────

  async starting(): Promise<void> {
    if (!this.active) return;
    await this.connection.ensureConnected();
    this.send(COMPANION_STATUS.starting);
  }

  thinking(): void {
    if (!this.active || this.lastStatus === COMPANION_STATUS.thinking) return;
    this.send(COMPANION_STATUS.thinking);
  }

  toolStart(toolName: string, args: Record<string, string | undefined>): void {
    if (!this.active) return;
    const { status, detail } = statusForTool(toolName, args);
    this.send(status, detail);
  }

  toolError(toolName: string): void {
    if (!this.active) return;
    this.send(COMPANION_STATUS.error, toolName);
  }

  done(): void {
    if (!this.active) return;
    this.clearAttention();
    this.send(COMPANION_STATUS.done);
    setTimeout(() => {
      if (this.lastStatus === COMPANION_STATUS.done) this.sendRemove();
    }, 3000);
  }

  // ── attention bridge ─────────────────────────────────────────────────────────

  async requestAttention(data: unknown): Promise<void> {
    if (!this.active) return;
    const payload = parseAttentionRequest(data);
    if (!payload) return;
    if (!this.attention.request(payload.attentionId, this.lastStatus)) return;
    await this.connection.ensureConnected();
    this.send(COMPANION_STATUS.awaiting, payload.detail);
  }

  resolveAttention(data: unknown): void {
    const payload = parseAttentionResolve(data);
    if (!payload) return;
    const prior = this.attention.resolve(payload.attentionId);
    if (prior) this.send(prior);
  }

  clearAttention(): void {
    const prior = this.attention.clear();
    if (prior) this.send(prior);
  }

  shutdown(): void {
    this.clearAttention();
    this.teardown();
  }

  // ── internals ────────────────────────────────────────────────────────────────

  private async loadGlimpse(): Promise<void> {
    if (this.glimpseLoaded) return;
    this.glimpseLoaded = true;
    this.followCursorSupport = await loadFollowCursorSupport();
  }

  private maybeNotifyUnsupported(ctx: ExtensionContext): void {
    if (this.followCursorSupport.supported || this.warnedUnsupported) return;
    this.warnedUnsupported = true;
    ctx.ui.notify(
      `Companion disabled on this platform: ${this.followCursorSupport.reason}`,
      "info",
    );
  }

  private send(status: CompanionStatus, detail?: string): void {
    this.lastStatus = status;
    if (!this.connection.isConnected) return;
    const msg: CompanionMessage = { id: SESSION_ID, project: this.project, status, detail };
    if (this.lastCtx) {
      try {
        const usage = this.lastCtx.getContextUsage();
        if (usage && usage.percent != null) {
          msg.contextPercent = Math.round(usage.percent);
        }
      } catch {}
    }
    this.connection.write(msg);
  }

  private sendRemove(): void {
    if (!this.connection.isConnected) return;
    this.connection.write({ id: SESSION_ID, type: "remove" });
    this.lastStatus = "";
  }

  private teardown(): void {
    if (this.connection.isConnected) this.sendRemove();
    this.connection.end();
    this.lastStatus = "";
  }
}
