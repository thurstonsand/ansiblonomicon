import { randomUUID } from "node:crypto";
import { basename } from "node:path";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import type { CompanionUpdateMessage } from "../shared/messages.js";
import { COMPANION_STATUS, type CompanionStatusLabel } from "../shared/status.js";
import { statusForTool, statusForToolCallUpdate, type ToolCallUpdate } from "./activity.js";
import { AttentionTracker, parseAttentionRequest, parseAttentionResolve } from "./attention.js";
import { CompanionConnection } from "./connection.js";
import {
  type FollowCursorSupport,
  loadFollowCursorSupport,
  resolveNode,
} from "./glimpse-support.js";
import { loadCompanionSettings } from "./settings.js";
import { buildCompanionThemeForContext } from "./theme.js";

const SESSION_ID = randomUUID().slice(0, 8);

/**
 * Owns the mutable per-session companion state and translates pi activity into
 * socket messages. Event registration lives in handlers.ts / command.ts; this
 * class exposes the intent-level operations they call.
 */
export class CompanionSession {
  private readonly settings = loadCompanionSettings();
  private enabled = this.settings.enabled;
  private lastStatus: CompanionStatusLabel | "" = "";
  private lastDetail: string | undefined;
  private lastCtx: ExtensionContext | null = null;
  private warnedUnsupported = false;
  private followCursorSupport: FollowCursorSupport = { supported: true };
  private glimpseLoaded = false;
  private readonly project = basename(process.cwd());
  private readonly connection = new CompanionConnection();
  private readonly attention = new AttentionTracker();

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

  responding(): void {
    if (!this.active || this.lastStatus === COMPANION_STATUS.responding) return;
    this.send(COMPANION_STATUS.responding);
  }

  toolCallUpdate(update: ToolCallUpdate): void {
    if (!this.active) return;
    const { status, detail } = statusForToolCallUpdate(update, this.settings.tools);
    this.send(status, detail);
  }

  toolStart(toolName: string, args: Record<string, unknown>): void {
    if (!this.active) return;
    const { status, detail } = statusForTool(toolName, args, this.settings.tools);
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
    if (!this.attention.request(payload.attentionId, payload.label)) return;
    await this.connection.ensureConnected();
    this.resend();
  }

  resolveAttention(data: unknown): void {
    const payload = parseAttentionResolve(data);
    if (!payload) return;
    if (this.attention.resolve(payload.attentionId)) this.resend();
  }

  clearAttention(): void {
    if (this.attention.clear()) this.resend();
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

  private send(status: CompanionStatusLabel, detail?: string): void {
    if (this.lastStatus === status && this.lastDetail === detail) return;
    this.lastStatus = status;
    this.lastDetail = detail;
    this.resend();
  }

  private resend(): void {
    if (!this.connection.isConnected || !this.lastStatus) return;
    const msg: CompanionUpdateMessage = {
      id: SESSION_ID,
      project: this.project,
      status: this.lastStatus,
      detail: this.lastDetail,
      attention: this.attention.active,
      attentionLabel: this.attention.label,
    };
    if (this.lastCtx) {
      msg.theme = buildCompanionThemeForContext(this.lastCtx);
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
