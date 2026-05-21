#!/usr/bin/env node

// ==============================================================
// BLOCKLIST: git mutations that force "ask" permission
// ==============================================================
const FORCE_ASK_PATTERNS = [
  { label: "git stash", pattern: /\bgit\s+(\S+\s+)*?stash\b/ },
  { label: "git add", pattern: /\bgit\s+(\S+\s+)*?add\b/ },
  { label: "git commit", pattern: /\bgit\s+(\S+\s+)*?commit\b/ },
  { label: "git push", pattern: /\bgit\s+(\S+\s+)*?push\b/ },
  { label: "git checkout", pattern: /\bgit\s+(\S+\s+)*?checkout\b/ },
  { label: "git reset", pattern: /\bgit\s+(\S+\s+)*?reset\b/ },
  { label: "git clean", pattern: /\bgit\s+(\S+\s+)*?clean\b/ },
  { label: "git rebase", pattern: /\bgit\s+(\S+\s+)*?rebase\b/ },
  { label: "git branch -d/-D", pattern: /\bgit\s+(\S+\s+)*?branch\s+(\S+\s+)*?-[dD]\b/ },
];

async function main() {
  let input = "";

  process.stdin.setEncoding("utf-8");

  for await (const chunk of process.stdin) {
    input += chunk;
  }

  let data;
  try {
    data = JSON.parse(input);
  } catch {
    process.exit(0);
  }

  const toolName = data.tool_name || "";
  const toolInput = data.tool_input || {};

  if (toolName !== "Bash") {
    process.exit(0);
  }

  const command = toolInput.command || "";

  for (const { label, pattern } of FORCE_ASK_PATTERNS) {
    if (pattern.test(command)) {
      console.log(
        JSON.stringify({
          hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "ask",
            permissionDecisionReason: `Authorization required: git mutation (${label})`,
          },
        }),
      );
      process.exit(0);
    }
  }

  process.exit(0);
}

main();
