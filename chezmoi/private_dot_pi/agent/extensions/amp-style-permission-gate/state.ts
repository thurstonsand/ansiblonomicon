import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

type PermissionGateState = { enabled: boolean };

const STATE_TYPE = "amp-style-permission-gate";

export function persistPermissionGateState(pi: ExtensionAPI, enabled: boolean): void {
  pi.appendEntry<PermissionGateState>(STATE_TYPE, { enabled });
}

export function restorePermissionGateState(ctx: ExtensionContext): boolean {
  const last = ctx.sessionManager
    .getBranch()
    .findLast((entry) => entry.type === "custom" && entry.customType === STATE_TYPE);

  if (last?.type !== "custom") return true;
  return (last.data as PermissionGateState).enabled ?? true;
}
