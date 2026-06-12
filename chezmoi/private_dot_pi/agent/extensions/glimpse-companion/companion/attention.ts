import { type Static, Type } from "typebox";
import { safeParseTypeBoxValue } from "./typebox.js";

/**
 * The attention event protocol on pi's in-process bus. Any extension can emit
 * these to raise/clear a companion callout; namespaced under `glimpseui:`.
 */
export const ATTENTION_REQUEST = "glimpseui:attention:request";
export const ATTENTION_RESOLVE = "glimpseui:attention:resolve";

const AttentionRequestSchema = Type.Object({
  attentionId: Type.String(),
  kind: Type.Optional(Type.String()),
  detail: Type.Optional(Type.String()),
});

const AttentionResolveSchema = Type.Object({
  attentionId: Type.String(),
});

export type AttentionRequest = Static<typeof AttentionRequestSchema>;
export type AttentionResolve = Static<typeof AttentionResolveSchema>;

export function parseAttentionRequest(data: unknown): AttentionRequest | undefined {
  return safeParseTypeBoxValue(AttentionRequestSchema, data);
}

export function parseAttentionResolve(data: unknown): AttentionResolve | undefined {
  return safeParseTypeBoxValue(AttentionResolveSchema, data);
}

/**
 * Tracks outstanding "attention" spans for one session. UUID correlation ids
 * make resolution race-safe: a resolve for an unknown id is a no-op, and the
 * pill only clears when the last outstanding span resolves.
 */
export class AttentionTracker<S = string> {
  private readonly outstanding = new Set<string>();
  private priorStatus: S | null = null;

  /** Returns true when this is the first span (caller should show "awaiting"). */
  request(id: string, currentStatus: S): boolean {
    const wasEmpty = this.outstanding.size === 0;
    this.outstanding.add(id);
    if (!wasEmpty) return false;
    this.priorStatus = currentStatus;
    return true;
  }

  /** Returns the status to restore when the last span resolves, else null. */
  resolve(id: string): S | null {
    if (!this.outstanding.delete(id)) return null;
    if (this.outstanding.size > 0) return null;
    return this.take();
  }

  /** Drops all outstanding spans, returning the status to restore, else null. */
  clear(): S | null {
    if (this.outstanding.size === 0) return null;
    this.outstanding.clear();
    return this.take();
  }

  private take(): S | null {
    const prior = this.priorStatus;
    this.priorStatus = null;
    return prior;
  }
}
