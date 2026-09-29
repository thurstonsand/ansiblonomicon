import { existsSync, readFileSync } from "node:fs";
import { basename, delimiter, join } from "node:path";
import {
  DefaultPackageManager,
  getAgentDir,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

export interface FollowCursorSupport {
  supported: boolean;
  reason?: string;
}

// glimpseui is a user-scope pi package: npm on personal hosts, a git clone on
// work hosts whose registry lacks it. Pi's package manager is the one authority
// on where either install lives.
export function resolveGlimpseEntry(): string | null {
  const agentDir = getAgentDir();
  const cwd = process.cwd();
  const packageManager = new DefaultPackageManager({
    cwd,
    agentDir,
    settingsManager: SettingsManager.create(cwd, agentDir),
  });
  for (const { scope, installedPath } of packageManager.listConfiguredPackages()) {
    if (scope !== "user" || !installedPath) continue;
    const manifest = join(installedPath, "package.json");
    if (!existsSync(manifest)) continue;
    if (JSON.parse(readFileSync(manifest, "utf-8")).name === "glimpseui") {
      return join(installedPath, "src", "glimpse.mjs");
    }
  }
  return null;
}

// pi ships as a compiled binary, so process.execPath points at pi, not node.
// Spawning it would relaunch pi with companion.ts as a prompt and recurse
// into an unbounded fan-out of sessions. Resolve a real node interpreter.
export function resolveNode(): string | null {
  const override = process.env.GLIMPSE_NODE;
  if (override && existsSync(override)) return override;
  if (basename(process.execPath).toLowerCase().startsWith("node")) {
    return process.execPath;
  }
  const exe = process.platform === "win32" ? "node.exe" : "node";
  for (const dir of (process.env.PATH ?? "").split(delimiter)) {
    if (!dir) continue;
    const candidate = join(dir, exe);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

export async function loadFollowCursorSupport(): Promise<FollowCursorSupport> {
  const entry = resolveGlimpseEntry();
  if (!entry) return { supported: false, reason: "glimpseui is not an installed pi package" };
  try {
    const mod = (await import(entry)) as {
      getFollowCursorSupport?: () => FollowCursorSupport;
    };
    if (typeof mod.getFollowCursorSupport === "function") {
      return mod.getFollowCursorSupport();
    }
    return { supported: true };
  } catch (err) {
    return {
      supported: false,
      reason: err instanceof Error ? err.message : String(err),
    };
  }
}
