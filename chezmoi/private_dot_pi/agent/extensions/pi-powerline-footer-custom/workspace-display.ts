import { execSync } from "node:child_process";
import { basename } from "node:path";
import type { ExtensionContext, ThemeColor } from "@earendil-works/pi-coding-agent";
import { getCapabilities, hyperlink } from "@earendil-works/pi-tui";

import { getJiraSettings } from "./settings.js";

const FOLDER_STATUS_KEY = "workspace_folder";
const BRANCH_STATUS_KEY = "workspace_branch";
const FOLDER_ICON = "\u{F115}";
const BRANCH_ICON = "\u{F126}";
const MAINLINE_BRANCHES = new Set(["main", "master"]);
const JIRA_TICKET_PATTERN = /[A-Z][A-Z0-9]+-\d+/;

export function updateWorkspaceDisplayStatuses(ctx: ExtensionContext): void {
  updateFolderStatus(ctx);
  updateBranchStatus(ctx, currentGitBranch(ctx.cwd));
}

function updateFolderStatus(ctx: ExtensionContext): void {
  ctx.ui.setStatus(
    FOLDER_STATUS_KEY,
    ctx.ui.theme.fg("bashMode", `${FOLDER_ICON} ${basename(ctx.cwd) || ctx.cwd}`),
  );
}

function updateBranchStatus(ctx: ExtensionContext, branch: string | null): void {
  if (!branch) {
    ctx.ui.setStatus(BRANCH_STATUS_KEY, undefined);
    return;
  }

  const color = branchColor(branch);
  const link = ticketLink(branch);
  if (!link) {
    ctx.ui.setStatus(BRANCH_STATUS_KEY, ctx.ui.theme.fg(color, `${BRANCH_ICON} ${branch}`));
    return;
  }

  // The ticket is colored as a link (blue) and wrapped in an OSC 8 hyperlink;
  // the surrounding branch keeps its own color. Each fg() call self-resets, so
  // the segments concatenate without color bleed.
  const text =
    ctx.ui.theme.fg(color, `${BRANCH_ICON} ${link.before}`) +
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
