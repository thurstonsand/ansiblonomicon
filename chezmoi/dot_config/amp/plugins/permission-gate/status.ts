import type { PluginAPI } from "@ampcode/plugin";
import type { PermissionGateState, PermissionGateStatus, ThreadID } from "./state.ts";

export function statusText(status: PermissionGateStatus): string {
  return `permissions:${status}`;
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
    text: statusText("on"),
    url: `command:${toggleCommandID}`,
  });

  function activeThreadID(): ThreadID | undefined {
    return amp.activeThread.current?.id;
  }

  function updateForThread(threadID: ThreadID | undefined): void {
    statusItem?.update({
      text: statusText(threadID ? state.status(threadID) : "on"),
      url: `command:${toggleCommandID}`,
    });
  }

  function updateForActiveThread(): void {
    updateForThread(activeThreadID());
  }

  amp.activeThread.subscribe((thread) => updateForThread(thread?.id));

  return { activeThreadID, updateForThread, updateForActiveThread };
}
