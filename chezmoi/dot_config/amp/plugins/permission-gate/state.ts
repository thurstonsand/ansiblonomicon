import type { ToolCallEvent } from "@ampcode/plugin";
import type { RuleKey } from "./rules.ts";

export type ThreadID = ToolCallEvent["thread"]["id"];
export type PermissionGateStatus = "on" | "partial" | "off";

export class PermissionGateState {
  private readonly disabledThreads = new Set<ThreadID>();
  private readonly disabledRules = new Map<ThreadID, Set<RuleKey>>();

  isEnabled(threadID: ThreadID): boolean {
    return !this.disabledThreads.has(threadID);
  }

  isRuleEnabled(threadID: ThreadID, rule: RuleKey): boolean {
    return this.isEnabled(threadID) && !this.disabledRules.get(threadID)?.has(rule);
  }

  status(threadID: ThreadID): PermissionGateStatus {
    if (!this.isEnabled(threadID)) return "off";
    return this.disabledRules.has(threadID) ? "partial" : "on";
  }

  setEnabled(threadID: ThreadID, enabled: boolean): void {
    if (enabled) {
      this.disabledThreads.delete(threadID);
      this.disabledRules.delete(threadID);
      return;
    }

    this.disabledThreads.add(threadID);
  }

  disableRule(threadID: ThreadID, rule: RuleKey): void {
    const disabled = this.disabledRules.get(threadID) ?? new Set<RuleKey>();
    disabled.add(rule);
    this.disabledRules.set(threadID, disabled);
  }

  toggle(threadID: ThreadID): boolean {
    const enabled = !this.isEnabled(threadID);
    this.setEnabled(threadID, enabled);
    return enabled;
  }
}
