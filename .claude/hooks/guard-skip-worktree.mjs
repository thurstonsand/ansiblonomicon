#!/usr/bin/env node

import { execFileSync } from "node:child_process";

// Tier 1: anchored patterns — git subcommand at the start of a shell statement.
// Split command on statement boundaries first, then match.
const DENY_PATTERNS = [
  /^\s*git\s+pull\b/,
  /^\s*git\s+merge\b/,
  /^\s*git\s+rebase\b/,
  /^\s*git\s+stash\s+pop\b/,
];

// Tier 2: loose patterns — the words appear anywhere in the command text
// (heredoc body, commit message, echo, etc.). Forces a confirmation prompt.
const ASK_PATTERNS = [
  /\bgit\s+(\S+\s+)*?pull\b/,
  /\bgit\s+(\S+\s+)*?merge\b/,
  /\bgit\s+(\S+\s+)*?rebase\b/,
  /\bgit\s+(\S+\s+)*?stash\s+(\S+\s+)*?pop\b/,
];

const REASON =
  "uv.lock has skip-worktree set. Use `poe pull` instead — it handles the mask/unmask cycle.";

function hasSkipWorktree() {
  try {
    const out = execFileSync("git", ["ls-files", "-v", "uv.lock"], {
      encoding: "utf-8",
      timeout: 3000,
    }).trim();
    return out.startsWith("S ");
  } catch {
    return false;
  }
}

function splitStatements(command) {
  return command.split(/\s*(?:&&|\|\||[;|\n])\s*/);
}

function decide(decision) {
  console.log(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: decision,
        permissionDecisionReason: REASON,
      },
    }),
  );
  process.exit(0);
}

async function main() {
  let input = "";
  process.stdin.setEncoding("utf-8");
  for await (const chunk of process.stdin) input += chunk;

  let data;
  try {
    data = JSON.parse(input);
  } catch {
    process.exit(0);
  }

  if ((data.tool_name || "") !== "Bash") process.exit(0);

  const command = (data.tool_input || {}).command || "";

  if (!hasSkipWorktree()) process.exit(0);

  const segments = splitStatements(command);
  if (segments.some((s) => DENY_PATTERNS.some((p) => p.test(s)))) {
    decide("deny");
  }

  if (ASK_PATTERNS.some((p) => p.test(command))) {
    decide("ask");
  }
}

main();
