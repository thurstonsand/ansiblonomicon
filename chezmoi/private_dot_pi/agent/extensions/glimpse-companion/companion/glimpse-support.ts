import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { basename, delimiter, join } from "node:path";

export interface FollowCursorSupport {
  supported: boolean;
  reason?: string;
}

// glimpseui is installed as a global npm package, not under this extension's
// node_modules, so a bare import would not resolve at runtime. Locate its entry
// dynamically and import it lazily — this also keeps type-checking from
// requiring the package to be installed on machines that never run the
// companion (e.g. work hosts whose registry lacks glimpseui).
function resolveGlimpseEntry(): string | null {
  const candidates: string[] = [];
  const override = process.env.GLIMPSE_DIR;
  if (override) candidates.push(join(override, "src", "glimpse.mjs"));
  try {
    candidates.push(createRequire(import.meta.url).resolve("glimpseui"));
  } catch {}
  try {
    const root = execFileSync("npm", ["root", "-g"], { encoding: "utf-8" }).trim();
    if (root) candidates.push(join(root, "glimpseui", "src", "glimpse.mjs"));
  } catch {}
  return candidates.find((c) => existsSync(c)) ?? null;
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
  if (!entry) return { supported: false, reason: "glimpseui not found" };
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
