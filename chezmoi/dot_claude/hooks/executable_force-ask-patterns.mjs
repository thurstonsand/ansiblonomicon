#!/usr/bin/env node

// ==============================================================
// ALLOWLIST: safe patterns — checked first, short-circuits to pass
// ==============================================================
const ALLOW_PATTERNS = [
  /find\s+.*\s(-exec|-execdir)\s+(grep|ls|cat|head|tail|file|stat|wc|basename|dirname|readlink|sha256sum|md5sum)\b/,
];

// ==============================================================
// BLOCKLIST: patterns that force "ask" permission
// ==============================================================
const FORCE_ASK_PATTERNS = [
  /\bgit\s+(\S+\s+)*?stash\b/,
  /\bgit\s+(\S+\s+)*?add\b/,
  /\bgit\s+(\S+\s+)*?commit\b/,
  /\bgit\s+(\S+\s+)*?push\b/,
  /\bgit\s+(\S+\s+)*?checkout\b/,
  /\bgit\s+(\S+\s+)*?reset\b/,
  /\bgit\s+(\S+\s+)*?clean\b/,
  /\bgit\s+(\S+\s+)*?rebase\b/,
  /\bgit\s+(\S+\s+)*?branch\s+(\S+\s+)*?-[dD]\b/,
  /rm\s+.*(-[rf].*-[rf]|-[rf]{2,}|--recursive.*--force|--force.*--recursive)/,
  /find\s+.*\s(-delete|-exec|-execdir)\b/,
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

  for (const pattern of ALLOW_PATTERNS) {
    if (pattern.test(command)) {
      process.exit(0);
    }
  }

  for (const pattern of FORCE_ASK_PATTERNS) {
    if (pattern.test(command)) {
      console.log(
        JSON.stringify({
          hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "ask",
            permissionDecisionReason: `Command matches pattern: ${pattern}`,
          },
        }),
      );
      process.exit(0);
    }
  }

  process.exit(0);
}

main();
