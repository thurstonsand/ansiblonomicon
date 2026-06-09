#!/usr/bin/env bun
// Claude Code session-recovery recorder.
//
// A Claude hook (SessionStart / Stop / SessionEnd) fires this with the hook
// payload on stdin. It maps the lifecycle onto the shared recovery core:
//   SessionStart / Stop -> writeRecord  (Stop also refreshes a late title)
//   SessionEnd          -> deleteRecord (terminal; nothing left to recover)
//
// SessionEnd is the single delete authority and fires on every terminal
// transition, /clear included. A hard restart fires no SessionEnd, so the file
// survives -- that survivor is the recovery signal the `sessions` CLI consumes.
import { appendFileSync, readFileSync } from "node:fs";
import { deleteRecord, writeRecord } from "@thurstons/session-recovery";

const LOG_PATH = "/tmp/claude-session-recovery.log";

/**
 * The subset of Claude's hook stdin payload this recorder consumes, parsed and
 * validated from untyped JSON.
 */
class HookEvent {
	private constructor(
		readonly sessionId: string,
		readonly event: string,
		readonly cwd: string,
		readonly transcriptPath: string | null,
		readonly reason: string | null,
	) {}

	get isTerminal(): boolean {
		return this.event === "SessionEnd";
	}

	static parse(raw: string): HookEvent {
		const data: unknown = JSON.parse(raw);
		if (typeof data !== "object" || data === null) {
			throw new TypeError("hook payload is not an object");
		}
		const obj = data as Record<string, unknown>;
		return new HookEvent(
			HookEvent.req(obj, "session_id"),
			HookEvent.req(obj, "hook_event_name"),
			HookEvent.opt(obj, "cwd") ?? "",
			HookEvent.opt(obj, "transcript_path"),
			HookEvent.opt(obj, "reason"),
		);
	}

	/** Required string field; throws if missing or not a string. */
	private static req(obj: Record<string, unknown>, key: string): string {
		const value = obj[key];
		if (typeof value !== "string" || value === "") {
			throw new TypeError(`hook payload missing required string '${key}'`);
		}
		return value;
	}

	/** Optional string field; null when absent, throws if present but not a string. */
	private static opt(obj: Record<string, unknown>, key: string): string | null {
		const value = obj[key];
		if (value === undefined || value === null) {
			return null;
		}
		if (typeof value !== "string") {
			throw new TypeError(`hook payload field '${key}' must be a string`);
		}
		return value;
	}
}

function log(sessionId: string, msg: string): void {
	try {
		const ts = new Date().toISOString();
		appendFileSync(
			LOG_PATH,
			`[${ts}] ppid=${process.ppid} session=${sessionId} ${msg}\n`,
		);
	} catch {
		// Best-effort debug log; never fail the hook over it.
	}
}

/** Most recent custom title from the transcript, or null. */
function readTitle(transcript: string | null): string | null {
	if (!transcript) {
		return null;
	}
	let title: string | null = null;
	try {
		for (const raw of readFileSync(transcript, "utf8").split("\n")) {
			const line = raw.trim();
			if (!line) {
				continue;
			}
			try {
				const entry = JSON.parse(line);
				if (entry.type === "custom-title") {
					title = entry.customTitle ?? null;
				}
			} catch {
				// Skip malformed JSONL lines.
			}
		}
	} catch {
		return null;
	}
	return title;
}

async function readStdin(): Promise<string> {
	const chunks: Buffer[] = [];
	for await (const chunk of process.stdin) {
		chunks.push(chunk as Buffer);
	}
	return Buffer.concat(chunks).toString("utf8");
}

async function main(): Promise<void> {
	let hook: HookEvent;
	try {
		hook = HookEvent.parse(await readStdin());
	} catch {
		return;
	}

	log(hook.sessionId, `event=${hook.event} cwd=${hook.cwd}`);

	if (hook.isTerminal) {
		deleteRecord("claude", hook.sessionId);
		log(hook.sessionId, `removed own file (SessionEnd reason=${hook.reason})`);
		return;
	}

	writeRecord({
		tool: "claude",
		sessionId: hook.sessionId,
		name: readTitle(hook.transcriptPath),
		cwd: hook.cwd,
		transcript: hook.transcriptPath,
		pid: process.ppid,
	});
	log(hook.sessionId, "wrote record");
}

main();
