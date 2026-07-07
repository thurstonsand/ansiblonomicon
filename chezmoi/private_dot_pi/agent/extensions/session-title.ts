import { execFileSync } from "node:child_process";
import { realpathSync } from "node:fs";
import path from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const MAINLINE_BRANCHES = new Set(["main", "master"]);

function git(cwd: string, args: string[]): string | null {
  try {
    return (
      execFileSync("git", ["-C", cwd, ...args], {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
      }).trim() || null
    );
  } catch {
    return null;
  }
}

function normalizeGitPath(cwd: string, gitPath: string): string {
  const absolutePath = path.isAbsolute(gitPath) ? gitPath : path.resolve(cwd, gitPath);

  try {
    return realpathSync.native(absolutePath);
  } catch {
    return path.normalize(absolutePath);
  }
}

function isInGitRepo(cwd: string): boolean {
  return git(cwd, ["rev-parse", "--is-inside-work-tree"]) === "true";
}

function isLinkedWorktree(cwd: string): boolean {
  const gitDir = git(cwd, ["rev-parse", "--git-dir"]);
  const commonDir = git(cwd, ["rev-parse", "--git-common-dir"]);

  if (!gitDir || !commonDir) return false;

  return normalizeGitPath(cwd, gitDir) !== normalizeGitPath(cwd, commonDir);
}

function currentBranch(cwd: string): string | null {
  return git(cwd, ["branch", "--show-current"]);
}

function shouldShowMainWorktreeBranch(branch: string | null): branch is string {
  if (!branch) return false;
  if (MAINLINE_BRANCHES.has(branch)) return false;
  if (branch === "HEAD" || branch.endsWith("/HEAD")) return false;
  return true;
}

function titleFor(cwd: string): string {
  const cwdName = path.basename(cwd) || cwd;

  if (!isInGitRepo(cwd)) return `pi:${cwdName}`;

  const branch = currentBranch(cwd);

  if (isLinkedWorktree(cwd)) {
    return branch ? `pi:wt:${cwdName}:${branch}` : `pi:wt:${cwdName}`;
  }

  return shouldShowMainWorktreeBranch(branch) ? `pi:${cwdName}:${branch}` : `pi:${cwdName}`;
}

export default function sessionTitle(pi: ExtensionAPI): void {
  const resetTitle = (ctx: ExtensionContext, defer = false): void => {
    const title = titleFor(ctx.cwd);
    ctx.ui.setTitle(title);
    if (defer) setTimeout(() => ctx.ui.setTitle(title), 0);
  };

  pi.on("session_start", (_event, ctx) => {
    resetTitle(ctx, true);
  });

  pi.on("session_info_changed", (_event, ctx) => {
    resetTitle(ctx);
  });

  pi.on("session_tree", (_event, ctx) => {
    resetTitle(ctx);
  });

  pi.on("session_compact", (_event, ctx) => {
    resetTitle(ctx);
  });
}
