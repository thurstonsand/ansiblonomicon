#!/usr/bin/env node

import { execFile } from "node:child_process";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HOOK = join(
  dirname(fileURLToPath(import.meta.url)),
  "guard-skip-worktree.mjs",
);

function skipWorktreeIsSet() {
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

const swSet = skipWorktreeIsSet();
console.log(`skip-worktree on uv.lock: ${swSet}\n`);

// [command, expectedWhenSW, expectedWithoutSW, description]
const cases = [
  // Tier 1: deny — bare git commands
  ["git pull", "deny", "pass", "git pull"],
  ["git pull --rebase origin main", "deny", "pass", "git pull --rebase"],
  ["git merge feature-branch", "deny", "pass", "git merge"],
  ["git rebase main", "deny", "pass", "git rebase"],
  ["git stash pop", "deny", "pass", "git stash pop"],
  ["git stash pop --index", "deny", "pass", "git stash pop --index"],
  ["git status && git pull", "deny", "pass", "chained: git pull after &&"],

  // Tier 2: ask — git commands mentioned in string content
  [
    `cat > /tmp/msg.txt << 'EOF'\nuse poe pull instead of git pull\nEOF\ngit commit -F /tmp/msg.txt`,
    "ask",
    "pass",
    "git pull inside heredoc body",
  ],
  [
    `echo "don't run git merge here"`,
    "ask",
    "pass",
    "git merge inside echo string",
  ],
  [
    `git commit -m "why: git pull breaks with skip-worktree"`,
    "ask",
    "pass",
    "git pull inside -m argument",
  ],

  // Should NOT match at all
  ["git stash", "pass", "pass", "git stash (not pop)"],
  ["git stash list", "pass", "pass", "git stash list"],
  ["git status", "pass", "pass", "git status"],
  ["git diff", "pass", "pass", "git diff"],
  ["git log --oneline", "pass", "pass", "git log"],
  ["git push origin main", "pass", "pass", "git push"],
  ["git add .", "pass", "pass", "git add"],
  ["git commit -m 'test'", "pass", "pass", "git commit"],
  ["uv run poe pull", "pass", "pass", "poe pull (safe alternative)"],

  // Non-Bash tool
  [
    null,
    "pass",
    "pass",
    "non-Bash tool",
    { tool_name: "Read", tool_input: { file_path: "/tmp/foo" } },
  ],
];

let passed = 0;
let failed = 0;

for (const [command, expectedSW, expectedNoSW, desc, override] of cases) {
  const expected = swSet ? expectedSW : expectedNoSW;
  const input = override ?? { tool_name: "Bash", tool_input: { command } };

  const result = await new Promise((resolve, reject) => {
    const child = execFile("node", [HOOK], (err, stdout) => {
      if (err) return reject(err);
      resolve(stdout.trim());
    });
    child.stdin.end(JSON.stringify(input));
  });

  let actual;
  if (result.includes('"deny"')) actual = "deny";
  else if (result.includes('"ask"')) actual = "ask";
  else actual = "pass";

  if (actual === expected) {
    passed++;
  } else {
    failed++;
    console.log(
      `FAIL: ${desc}\n  command:  ${command}\n  expected: ${expected}\n  got:      ${actual}\n`,
    );
  }
}

console.log(`\n${passed} passed, ${failed} failed, ${passed + failed} total`);
process.exit(failed > 0 ? 1 : 0);
