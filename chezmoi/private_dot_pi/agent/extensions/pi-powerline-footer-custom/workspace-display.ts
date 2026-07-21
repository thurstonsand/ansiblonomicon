import { execSync } from "node:child_process";
import { basename, dirname } from "node:path";
import type { ExtensionContext, ThemeColor } from "@earendil-works/pi-coding-agent";
import { getCapabilities, hyperlink } from "@earendil-works/pi-tui";

import { getJiraSettings } from "./settings.js";

const FOLDER_STATUS_KEY = "workspace_folder";
const BRANCH_STATUS_KEY = "workspace_branch";
const FOLDER_ICON = "\u{F115}";
const BRANCH_ICON = "\u{F126}";
const WORKTREE_ICON = "\u{E725}";
const MAINLINE_BRANCHES = new Set(["main", "master"]);
const JIRA_TICKET_PATTERN = /[A-Z][A-Z0-9]+-\d+/;

export function updateWorkspaceDisplayStatuses(ctx: ExtensionContext): void {
  updateFolderStatus(ctx);
  updateBranchStatus(ctx, currentGitBranch(ctx.cwd), isLinkedWorktree(ctx.cwd));
}

function updateFolderStatus(ctx: ExtensionContext): void {
  const folder = mainWorktreeName(ctx.cwd) ?? (basename(ctx.cwd) || ctx.cwd);
  ctx.ui.setStatus(FOLDER_STATUS_KEY, ctx.ui.theme.fg("bashMode", `${FOLDER_ICON} ${folder}`));
}

// In a linked worktree, the common git dir points at the main worktree's .git,
// so its parent is the main worktree folder. Outside a worktree this returns
// the current repo's folder, matching the previous basename(cwd) behavior.
function mainWorktreeName(cwd: string): string | null {
  try {
    const commonDir = execSync("git rev-parse --path-format=absolute --git-common-dir", {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    if (!commonDir) return null;
    return basename(dirname(commonDir)) || null;
  } catch {
    return null;
  }
}

// A linked worktree has a per-worktree git dir distinct from the shared common
// dir; in the main worktree the two paths are identical.
function isLinkedWorktree(cwd: string): boolean {
  try {
    const output = execSync("git rev-parse --path-format=absolute --git-dir --git-common-dir", {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    const [gitDir, commonDir] = output.split("\n");
    return Boolean(gitDir && commonDir && gitDir !== commonDir);
  } catch {
    return false;
  }
}

function updateBranchStatus(ctx: ExtensionContext, branch: string | null, worktree: boolean): void {
  if (!branch) {
    ctx.ui.setStatus(BRANCH_STATUS_KEY, undefined);
    return;
  }

  const color = branchColor(branch);
  const prefix = worktree ? `${WORKTREE_ICON} ${BRANCH_ICON}` : BRANCH_ICON;
  const link = ticketLink(branch);
  if (!link) {
    ctx.ui.setStatus(BRANCH_STATUS_KEY, ctx.ui.theme.fg(color, `${prefix} ${branch}`));
    return;
  }

  // The ticket is colored as a link (blue) and wrapped in an OSC 8 hyperlink;
  // the surrounding branch keeps its own color. Each fg() call self-resets, so
  // the segments concatenate without color bleed.
  const text =
    ctx.ui.theme.fg(color, `${prefix} ${link.before}`) +
    hyperlink(ctx.ui.theme.fg("accent", link.ticket), link.url) +
    ctx.ui.theme.fg(color, link.after);
  ctx.ui.setStatus(BRANCH_STATUS_KEY, text);
}

interface TicketLink {
  before: string;
  ticket: string;
  after: string;
  url: string;
}

function ticketLink(branch: string): TicketLink | undefined {
  const baseUrl = getJiraSettings().browseUrl;
  if (!baseUrl || !getCapabilities().hyperlinks) return undefined;

  const match = branch.match(JIRA_TICKET_PATTERN);
  if (!match || match.index === undefined) return undefined;

  const ticket = match[0];
  return {
    before: branch.slice(0, match.index),
    ticket,
    after: branch.slice(match.index + ticket.length),
    url: `${baseUrl}${ticket}`,
  };
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
