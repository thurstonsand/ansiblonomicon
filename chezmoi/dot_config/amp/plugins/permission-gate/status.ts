import type { PluginAPI } from "@ampcode/plugin";
import type { PermissionGateState, ThreadID } from "./state.ts";

export function statusText(enabled: boolean): string {
  return enabled ? "permissions:on" : "permissions:off";
}

export type PermissionStatus = {
  activeThreadID: () => ThreadID | undefined;
  updateForThread: (threadID: ThreadID | undefined) => void;
  updateForActiveThread: () => void;
};

export function registerPermissionStatus(
  amp: PluginAPI,
  state: PermissionGateState,
  toggleCommandID: string,
): PermissionStatus {
  const statusItem = amp.experimental?.createStatusItem({
    text: statusText(true),
    url: `command:${toggleCommandID}`,
  });

  function activeThreadID(): ThreadID | undefined {
    return amp.experimental?.activeThread.current?.id;
  }

  function updateForThread(threadID: ThreadID | undefined): void {
    statusItem?.update({
      text: statusText(threadID ? state.isEnabled(threadID) : true),
      url: `command:${toggleCommandID}`,
    });
  }

  function updateForActiveThread(): void {
    updateForThread(activeThreadID());
  }

  amp.experimental?.activeThread.subscribe((thread) => updateForThread(thread?.id));

  return { activeThreadID, updateForThread, updateForActiveThread };
}
