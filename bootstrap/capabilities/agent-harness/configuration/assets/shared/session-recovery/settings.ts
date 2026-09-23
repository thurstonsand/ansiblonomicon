import { readFileSync, realpathSync } from "node:fs";
import { homedir } from "node:os";
import { isAbsolute, join, relative, resolve, sep } from "node:path";
import { z } from "zod";

const SettingsSchema = z.object({
	ignoredDirectories: z.array(z.string()).default([]),
});

type SettingsData = z.infer<typeof SettingsSchema>;

export class Settings {
	readonly ignoredDirectories: readonly string[];

	constructor(data: SettingsData) {
		this.ignoredDirectories = data.ignoredDirectories;
	}

	shouldTrackCwd(cwd: string): boolean {
		for (const ignored of this.ignoredDirectories) {
			if (sameOrChildDir(cwd, ignored)) {
				return false;
			}
		}
		return true;
	}
}

export function settingsPath(): string {
	const base = process.env.XDG_CONFIG_HOME || join(homedir(), ".config");
	return join(base, "session-recovery", "config.json");
}

export function loadSettings(): Settings {
	return new Settings(readSettingsData());
}

function readSettingsData(): SettingsData {
	try {
		return SettingsSchema.parse(
			JSON.parse(readFileSync(settingsPath(), "utf8")),
		);
	} catch {
		return SettingsSchema.parse({});
	}
}

function normalizeDir(path: string): string {
	let expanded = path;
	if (expanded === "~" || expanded.startsWith("~/")) {
		expanded = join(homedir(), expanded.slice(2));
	}
	const absolute = isAbsolute(expanded) ? expanded : resolve(expanded);
	try {
		return realpathSync(absolute);
	} catch {
		return resolve(absolute);
	}
}

function sameOrChildDir(path: string, dir: string): boolean {
	if (!path || !dir) {
		return false;
	}
	const rel = relative(normalizeDir(dir), normalizeDir(path));
	return rel === "" || (rel !== ".." && !rel.startsWith(`..${sep}`));
}
