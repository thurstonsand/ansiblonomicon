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
  label: Type.Optional(Type.String()),
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
 * Tracks outstanding "attention" spans for one session. Attention annotates the
 * current companion state; it does not replace the active tool status.
 */
export class AttentionTracker {
  private readonly outstanding = new Map<string, string | undefined>();

  get active(): boolean {
    return this.outstanding.size > 0;
  }

  get label(): string | undefined {
    return Array.from(this.outstanding.values()).findLast((label) => label !== undefined);
  }

  request(id: string, label?: string): boolean {
    const before = this.snapshot();
    this.outstanding.set(id, this.normalizeLabel(label));
    return before !== this.snapshot();
  }

  resolve(id: string): boolean {
    const before = this.snapshot();
    this.outstanding.delete(id);
    return before !== this.snapshot();
  }

  clear(): boolean {
    if (this.outstanding.size === 0) return false;
    this.outstanding.clear();
    return true;
  }

  private normalizeLabel(label: string | undefined): string | undefined {
    const normalized = label?.trim();
    return normalized ? normalized : undefined;
  }

  private snapshot(): string {
    return `${this.active}:${this.label ?? ""}`;
  }
}
