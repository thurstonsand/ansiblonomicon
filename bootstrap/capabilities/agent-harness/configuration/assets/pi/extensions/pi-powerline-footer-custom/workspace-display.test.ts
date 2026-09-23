import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import { test } from "node:test";
import type { ExtensionContext, UserBashEvent } from "@earendil-works/pi-coding-agent";

import { WorkspaceDisplayStatus } from "./workspace-display.js";

test("renders the main worktree identity from a linked worktree", async (t) => {
  const cwd = mkdtempSync(join(tmpdir(), "powerline-main-"));
  const worktree = `${cwd}-linked`;
  t.after(() => {
    rmSync(worktree, { recursive: true, force: true });
    rmSync(cwd, { recursive: true, force: true });
  });

  runGit(cwd, ["init", "--quiet", "--initial-branch=main"]);
  runGit(cwd, ["config", "user.email", "test@example.com"]);
  runGit(cwd, ["config", "user.name", "Test"]);
  writeFileSync(join(cwd, "file.txt"), "content");
  runGit(cwd, ["add", "file.txt"]);
  runGit(cwd, ["commit", "--quiet", "-m", "initial"]);
  runGit(cwd, ["worktree", "add", "--quiet", "-b", "feature", worktree]);

  const statuses = new Map<string, string | undefined>();
  const display = new WorkspaceDisplayStatus();
  t.after(() => display.sessionShutdown());

  display.sessionStart(contextFor(worktree, statuses));
  await display.refresh(contextFor(worktree, statuses));

  assert.equal(statuses.get("workspace_folder"), ` ${basename(cwd)}`);
  assert.equal(statuses.get("workspace_branch"), "  feature");
});

test("invalidates the workspace after wt rebranch", async (t) => {
  const cwd = mkdtempSync(join(tmpdir(), "powerline-rebranch-"));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));

  runGit(cwd, ["init", "--quiet", "--initial-branch=main"]);
  runGit(cwd, ["config", "user.email", "test@example.com"]);
  runGit(cwd, ["config", "user.name", "Test"]);
  writeFileSync(join(cwd, "file.txt"), "content");
  runGit(cwd, ["add", "file.txt"]);
  runGit(cwd, ["commit", "--quiet", "-m", "initial"]);

  const statuses = new Map<string, string | undefined>();
  const display = new WorkspaceDisplayStatus();
  const ctx = contextFor(cwd, statuses);
  t.after(() => display.sessionShutdown());

  display.sessionStart(ctx);
  await display.refresh(ctx);
  assert.equal(statuses.get("workspace_branch"), " main");

  display.userBash({ command: "wt rebranch feature" } as UserBashEvent, ctx);
  runGit(cwd, ["switch", "--quiet", "-c", "feature"]);
  await new Promise((resolve) => setTimeout(resolve, 600));

  assert.equal(statuses.get("workspace_branch"), " feature");
});

test("renders the short SHA when the workspace has a detached HEAD", async (t) => {
  const cwd = mkdtempSync(join(tmpdir(), "powerline-workspace-"));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));

  runGit(cwd, ["init", "--quiet"]);
  runGit(cwd, ["config", "user.email", "test@example.com"]);
  runGit(cwd, ["config", "user.name", "Test"]);
  writeFileSync(join(cwd, "file.txt"), "content");
  runGit(cwd, ["add", "file.txt"]);
  runGit(cwd, ["commit", "--quiet", "-m", "initial"]);
  runGit(cwd, ["checkout", "--quiet", "--detach"]);
  const sha = runGit(cwd, ["rev-parse", "--short", "HEAD"]);

  const statuses = new Map<string, string | undefined>();
  const display = new WorkspaceDisplayStatus();
  t.after(() => display.sessionShutdown());

  display.sessionStart(contextFor(cwd, statuses));
  await display.refresh(contextFor(cwd, statuses));

  assert.equal(statuses.get("workspace_branch"), ` ${sha} (detached)`);
});

function contextFor(cwd: string, statuses: Map<string, string | undefined>): ExtensionContext {
  return {
    cwd,
    ui: {
      setStatus(key: string, value: string | undefined) {
        statuses.set(key, value);
      },
      theme: {
        fg(_color: string, text: string) {
          return text;
        },
      },
    },
  } as unknown as ExtensionContext;
}

function runGit(cwd: string, args: string[]): string {
  return execFileSync("git", args, { cwd, encoding: "utf8" }).trim();
}
