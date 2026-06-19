// @thurstons/session-recovery — shared session-recovery core.
//
// The single source of truth for the cross-agent recovery record. Consumed as a package
import { execFileSync } from "node:child_process";
import {
	type Dirent,
	mkdirSync,
	readdirSync,
	readFileSync,
	renameSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { homedir, platform } from "node:os";
import { join } from "node:path";
import { z } from "zod";
import type { Settings } from "./settings.ts";

export { loadSettings, Settings } from "./settings.ts";

export const SUPPORTED_TOOLS = ["pi", "claude"] as const;
export type Tool = (typeof SUPPORTED_TOOLS)[number];

/**
 * One live-or-orphaned session record. The `sessions` CLI consumes only these
 * files — never transcripts — so every field it needs lives here. Every agent's
 * recorder must produce this exact shape.
 */
export interface SessionRecord {
	sessionId: string;
	name: string | null;
	cwd: string;
	transcript: string | null;
	pid: number;
	bootId: string;
	updatedAt: number;
	tool: Tool;
}

export interface RecordInput {
	tool: Tool;
	sessionId: string;
	cwd: string;
	pid: number;
	name?: string | null;
	transcript?: string | null;
}

export function stateDir(tool: Tool): string {
	const base = process.env.XDG_STATE_HOME || join(homedir(), ".local", "state");
	return join(base, "session-recovery", tool);
}

let cachedBootId: string | undefined;

/**
 * Stable per-boot identifier, byte-identical across agents: the macOS boot
 * session UUID or the Linux kernel boot_id. Cross-tool dedup and prior-boot
 * detection depend on every producer using these same sources.
 */
export function bootId(): string {
	if (cachedBootId !== undefined) {
		return cachedBootId;
	}
	try {
		cachedBootId =
			platform() === "darwin"
				? execFileSync("sysctl", ["-n", "kern.bootsessionuuid"], {
						encoding: "utf8",
					}).trim()
				: readFileSync("/proc/sys/kernel/random/boot_id", "utf8").trim();
	} catch {
		cachedBootId = "";
	}
	return cachedBootId ?? "";
}

function recordPath(tool: Tool, sessionId: string): string {
	return join(stateDir(tool), `${sessionId}.json`);
}

const CleanupRecordSchema = z.object({
	sessionId: z.string(),
	cwd: z.string(),
});

type CleanupRecord = z.infer<typeof CleanupRecordSchema>;

function recordsForTool(tool: Tool): CleanupRecord[] {
	let entries: Dirent[];
	try {
		entries = readdirSync(stateDir(tool), { withFileTypes: true });
	} catch {
		return [];
	}

	const records: CleanupRecord[] = [];
	for (const entry of entries) {
		if (!entry.isFile() || !entry.name.endsWith(".json")) {
			continue;
		}
		const record = readRecordFile(join(stateDir(tool), entry.name));
		if (record) {
			records.push(record);
		}
	}
	return records;
}

function readRecordFile(path: string): CleanupRecord | null {
	try {
		return CleanupRecordSchema.parse(JSON.parse(readFileSync(path, "utf8")));
	} catch {
		return null;
	}
}

export function deleteIgnoredRecords(settings: Settings): void {
	for (const tool of SUPPORTED_TOOLS) {
		for (const record of recordsForTool(tool)) {
			if (!settings.shouldTrackCwd(record.cwd)) {
				deleteRecord(tool, record.sessionId);
			}
		}
	}
}

/** Atomically write (or refresh) a session's recovery record. */
export function writeRecord(input: RecordInput, settings: Settings): void {
	if (!settings.shouldTrackCwd(input.cwd)) {
		deleteRecord(input.tool, input.sessionId);
		return;
	}

	const dir = stateDir(input.tool);
	mkdirSync(dir, { recursive: true, mode: 0o700 });

	const record: SessionRecord = {
		sessionId: input.sessionId,
		name: input.name ?? null,
		cwd: input.cwd,
		transcript: input.transcript ?? null,
		pid: input.pid,
		bootId: bootId(),
		updatedAt: Date.now(),
		tool: input.tool,
	};

	const target = recordPath(input.tool, input.sessionId);
	const tmp = `${target}.tmp`;
	writeFileSync(tmp, `${JSON.stringify(record, null, 2)}\n`, { mode: 0o600 });
	renameSync(tmp, target);
}

/** Remove a session's record. Safe to call when nothing was ever written. */
export function deleteRecord(tool: Tool, sessionId: string): void {
	try {
		rmSync(recordPath(tool, sessionId));
	} catch {
		// Already gone, or never written (ephemeral session). Nothing to clean up.
	}
}
