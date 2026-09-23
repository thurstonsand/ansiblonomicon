import assert from "node:assert/strict";
import { findMatchingRule, type RuleKey } from "./rules.ts";
import type { PermissionSubject } from "./subjects.ts";

const shellCases: Array<{ command: string; rule?: RuleKey }> = [
  { command: "git status" },
  { command: "git add README.md", rule: "git-interference" },
  { command: "sudo git -C /repo commit -m test", rule: "git-interference" },
  { command: "git pull --rebase", rule: "git-interference" },
  { command: "git branch" },
  { command: "git branch -d old", rule: "git-interference" },
  { command: "git clean -n" },
  { command: "git clean -fd", rule: "git-interference" },
  { command: "echo 'git add README.md'" },
  { command: "rm -rf build", rule: "file-disposal" },
  { command: "rm -r build" },
  { command: "find . -name '*.tmp' -delete", rule: "file-disposal" },
  { command: "psql -c 'select * from users'" },
  { command: "psql -c 'update users set active = true'", rule: "database-integrity" },
  { command: "psql -c 'explain analyze select * from users'" },
  { command: "psql -c 'analyze users'", rule: "database-integrity" },
];

for (const testCase of shellCases) {
  const subject: PermissionSubject = {
    kind: "shell-command",
    toolName: "shell_command",
    command: testCase.command,
    detail: testCase.command,
  };
  const match = findMatchingRule(subject);
  assert.equal(match?.rule.key, testCase.rule, testCase.command);
}

const reconnaissance = findMatchingRule({
  kind: "tool-call",
  toolName: "web_search_web_search",
  input: { query: "internal system" },
  detail: '{"query":"internal system"}',
});
assert.equal(reconnaissance?.rule.key, "reconnaissance");

const builtInSearch = findMatchingRule({
  kind: "tool-call",
  toolName: "web_search",
  input: { query: "public docs" },
  detail: '{"query":"public docs"}',
});
assert.equal(builtInSearch, undefined);

console.log(`${shellCases.length + 2} permission rule cases passed`);
