import { execSync } from "node:child_process";
import { basename } from "node:path";
import type { ExtensionContext, ThemeColor } from "@mariozechner/pi-coding-agent";

const FOLDER_STATUS_KEY = "workspace_folder";
const BRANCH_STATUS_KEY = "workspace_branch";
const FOLDER_ICON = "\u{F115}";
const BRANCH_ICON = "\u{F126}";
const MAINLINE_BRANCHES = new Set(["main", "master"]);

export function updateWorkspaceDisplayStatuses(ctx: ExtensionContext): void {
  updateFolderStatus(ctx);
  updateBranchStatus(ctx);
}

function updateFolderStatus(ctx: ExtensionContext): void {
  ctx.ui.setStatus(
    FOLDER_STATUS_KEY,
    ctx.ui.theme.fg("bashMode", `${FOLDER_ICON} ${basename(ctx.cwd) || ctx.cwd}`),
  );
}

function updateBranchStatus(ctx: ExtensionContext): void {
  const branch = currentGitBranch(ctx.cwd);
  if (!branch) {
    ctx.ui.setStatus(BRANCH_STATUS_KEY, undefined);
    return;
  }

  ctx.ui.setStatus(
    BRANCH_STATUS_KEY,
    ctx.ui.theme.fg(branchColor(branch), `${BRANCH_ICON} ${branch}`),
  );
}

function branchColor(branch: string): ThemeColor {
  return MAINLINE_BRANCHES.has(branch) ? "warning" : "muted";
}

function currentGitBranch(cwd: string): string | null {
  try {
    return (
      execSync("git branch --show-current", {
        cwd,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
      }).trim() || null
    );
  } catch {
    return null;
  }
}
