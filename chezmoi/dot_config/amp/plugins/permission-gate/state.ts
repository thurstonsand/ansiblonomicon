import type { ToolCallEvent } from "@ampcode/plugin";

export type ThreadID = ToolCallEvent["thread"]["id"];

export class PermissionGateState {
	private readonly disabledThreads = new Set<ThreadID>();

	isEnabled(threadID: ThreadID): boolean {
		return !this.disabledThreads.has(threadID);
	}

	setEnabled(threadID: ThreadID, enabled: boolean): void {
		if (enabled) {
			this.disabledThreads.delete(threadID);
			return;
		}

		this.disabledThreads.add(threadID);
	}

	toggle(threadID: ThreadID): boolean {
		const enabled = !this.isEnabled(threadID);
		this.setEnabled(threadID, enabled);
		return enabled;
	}
}
