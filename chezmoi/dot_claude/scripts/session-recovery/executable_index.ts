#!/usr/bin/env bun
// Claude Code session-recovery recorder.
//
// A Claude hook (SessionStart / Stop / SessionEnd) fires this with the hook
// payload on stdin. It maps the lifecycle onto the shared recovery core:
//   SessionStart / Stop -> writeRecord  (Stop also refreshes a late title)
//   SessionEnd          -> delete only on a deliberate quit (see below)
//
// Not every SessionEnd means "done with this session." Claude fires it on
// abrupt termination too -- closing the terminal tab or a SIGHUP/SIGTERM all
// arrive as reason "other", indistinguishable from each other. Those are
// exactly the cases we want to remain recoverable. So we delete the record
// only on a deliberate in-app exit (Ctrl-D / `/exit` / `/quit` -> reason
// "prompt_input_exit", `/logout`, `/clear`); everything else -- tab close,
// kill signals, `resume`, and a hard reboot that fires no SessionEnd at all --
// leaves the record as the orphan the `sessions` CLI surfaces for recovery.
import { appendFileSync, readFileSync } from "node:fs";
import {
	deleteIgnoredRecords,
	deleteRecord,
	loadSettings,
	writeRecord,
} from "@thurstons/session-recovery";

const LOG_PATH = "/tmp/claude-session-recovery.log";

// SessionEnd reasons that mean the user deliberately ended the session in-app.
// Anything else (notably "other": tab close / SIGHUP / SIGTERM) is treated as
// recoverable and the record is kept.
const DELIBERATE_EXIT_REASONS = new Set([
	"prompt_input_exit",
	"logout",
	"clear",
]);

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

	/** True when this SessionEnd was a deliberate in-app quit, so the record
	 * should be removed rather than kept as a recoverable orphan. */
	get isDeliberateExit(): boolean {
		return (
			this.event === "SessionEnd" &&
			this.reason !== null &&
			DELIBERATE_EXIT_REASONS.has(this.reason)
		);
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

	const settings = loadSettings();
	deleteIgnoredRecords(settings);

	log(hook.sessionId, `event=${hook.event} reason=${hook.reason}`);

	if (hook.event === "SessionEnd") {
		// Deliberate quit -> remove. Abrupt end (tab close, signal) -> leave the
		// record in place so it surfaces as a recoverable orphan.
		if (hook.isDeliberateExit) {
			deleteRecord("claude", hook.sessionId);
			log(hook.sessionId, `removed own file (deliberate exit: ${hook.reason})`);
		} else {
			log(hook.sessionId, `kept as orphan (SessionEnd reason=${hook.reason})`);
		}
		return;
	}

	writeRecord(
		{
			tool: "claude",
			sessionId: hook.sessionId,
			name: readTitle(hook.transcriptPath),
			cwd: hook.cwd,
			transcript: hook.transcriptPath,
			pid: process.ppid,
		},
		settings,
	);
	log(hook.sessionId, "wrote record");
}

main();
