import { spawn } from "node:child_process";
import { basename, dirname } from "node:path";
import type {
  ExtensionContext,
  ThemeColor,
  ToolResultEvent,
  UserBashEvent,
} from "@earendil-works/pi-coding-agent";
import { getCapabilities, hyperlink } from "@earendil-works/pi-tui";

import { getJiraSettings } from "./settings.js";

const FOLDER_STATUS_KEY = "workspace_folder";
const BRANCH_STATUS_KEY = "workspace_branch";
const FOLDER_ICON = "\u{F115}";
const BRANCH_ICON = "\u{F126}";
const WORKTREE_ICON = "\u{E725}";
const MAINLINE_BRANCHES = new Set(["main", "master"]);
const JIRA_TICKET_PATTERN = /[A-Z][A-Z0-9]{2,}-\d+/;
const CACHE_TTL_MS = 500;

interface WorkspaceState {
  mainWorktreeName: string | null;
  branch: string | null;
  linkedWorktree: boolean;
}

interface CachedWorkspaceState {
  cwd: string;
  state: WorkspaceState;
  timestamp: number;
}

export class WorkspaceDisplayStatus {
  private cached: CachedWorkspaceState | undefined;
  private pending: { cwd: string; promise: Promise<WorkspaceState> } | undefined;
  private readonly timers = new Set<NodeJS.Timeout>();
  private generation = 0;
  private disposed = false;

  sessionStart(ctx: ExtensionContext): void {
    this.reset();
    void this.refresh(ctx);
  }

  turnEnd(ctx: ExtensionContext): void {
    void this.refresh(ctx);
  }

  toolResult(event: ToolResultEvent, ctx: ExtensionContext): void {
    if (event.toolName === "bash" && mightChangeWorkspace(String(event.input.command ?? ""))) {
      this.invalidate(ctx);
    }
  }

  userBash(event: UserBashEvent, ctx: ExtensionContext): void {
    if (mightChangeWorkspace(event.command)) this.scheduleInvalidation(ctx);
  }

  sessionShutdown(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.generation++;
    this.clearTimers();
  }

  async refresh(ctx: ExtensionContext, force = false): Promise<void> {
    if (this.disposed) return;

    const generation = ++this.generation;
    const cached = this.cached?.cwd === ctx.cwd ? this.cached : undefined;
    if (cached) {
      this.render(ctx, cached.state);
    } else {
      updateFolderStatus(ctx, basename(ctx.cwd) || ctx.cwd);
      updateBranchStatus(ctx, null, false);
    }

    if (!force && cached && Date.now() - cached.timestamp < CACHE_TTL_MS) return;

    const state = await this.fetch(ctx.cwd);
    if (this.disposed || generation !== this.generation) return;

    this.cached = { cwd: ctx.cwd, state, timestamp: Date.now() };
    this.render(ctx, state);
  }

  private invalidate(ctx: ExtensionContext): void {
    if (this.cached?.cwd === ctx.cwd) this.cached.timestamp = 0;
    void this.refresh(ctx, true);
  }

  private scheduleInvalidation(ctx: ExtensionContext): void {
    for (const delay of [100, 300, 500]) {
      const timer = setTimeout(() => {
        this.timers.delete(timer);
        if (!this.disposed) this.invalidate(ctx);
      }, delay);
      this.timers.add(timer);
    }
  }

  private reset(): void {
    this.generation++;
    this.disposed = false;
    this.cached = undefined;
    this.pending = undefined;
    this.clearTimers();
  }

  private clearTimers(): void {
    for (const timer of this.timers) clearTimeout(timer);
    this.timers.clear();
  }

  private fetch(cwd: string): Promise<WorkspaceState> {
    if (this.pending?.cwd === cwd) return this.pending.promise;

    const promise = fetchWorkspaceState(cwd).finally(() => {
      if (this.pending?.promise === promise) this.pending = undefined;
    });
    this.pending = { cwd, promise };
    return promise;
  }

  private render(ctx: ExtensionContext, state: WorkspaceState): void {
    updateFolderStatus(ctx, state.mainWorktreeName ?? (basename(ctx.cwd) || ctx.cwd));
    updateBranchStatus(ctx, state.branch, state.linkedWorktree);
  }
}

function mightChangeWorkspace(command: string): boolean {
  return [
    /\bgit\s+(checkout|switch|branch\s+-[dDmM]|merge|rebase|pull|reset|worktree)/,
    /\bgit\s+stash\s+(pop|apply)/,
    /\bwt\s+rebranch\b/,
  ].some((pattern) => pattern.test(command));
}

async function fetchWorkspaceState(cwd: string): Promise<WorkspaceState> {
  const [gitDirectories, currentBranch] = await Promise.all([
    runGit(cwd, ["rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir"]),
    runGit(cwd, ["branch", "--show-current"]),
  ]);

  if (gitDirectories === null || currentBranch === null) {
    return { mainWorktreeName: null, branch: null, linkedWorktree: false };
  }

  const [gitDir, commonDir] = gitDirectories.split("\n");
  const branch = currentBranch || (await detachedHead(cwd));
  return {
    mainWorktreeName: commonDir ? basename(dirname(commonDir)) || null : null,
    branch,
    linkedWorktree: Boolean(gitDir && commonDir && gitDir !== commonDir),
  };
}

async function detachedHead(cwd: string): Promise<string | null> {
  const sha = await runGit(cwd, ["rev-parse", "--short", "HEAD"]);
  return sha ? `${sha} (detached)` : "detached";
}

function runGit(cwd: string, args: string[]): Promise<string | null> {
  return new Promise((resolve) => {
    const child = spawn("git", args, { cwd, stdio: ["ignore", "pipe", "ignore"] });
    let stdout = "";
    let settled = false;

    const finish = (value: string | null): void => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      resolve(value);
    };

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.on("close", (code) => finish(code === 0 ? stdout.trim() : null));
    child.on("error", () => finish(null));

    const timeout = setTimeout(() => {
      child.kill();
      finish(null);
    }, 500);
  });
}

function updateFolderStatus(ctx: ExtensionContext, folder: string): void {
  ctx.ui.setStatus(FOLDER_STATUS_KEY, ctx.ui.theme.fg("bashMode", `${FOLDER_ICON} ${folder}`));
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
