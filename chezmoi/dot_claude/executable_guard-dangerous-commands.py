#!/usr/bin/env python3
import json
import re
import sys

DANGEROUS_PATTERNS = [
    r"\bgit\s+(\S+\s+)*?stash\b",
    r"\bgit\s+(\S+\s+)*?add\b",
    r"\bgit\s+(\S+\s+)*?commit\b",
    r"\bgit\s+(\S+\s+)*?push\b",
    r"\bgit\s+(\S+\s+)*?checkout\b",
    r"\bgit\s+(\S+\s+)*?reset\b",
    r"\bgit\s+(\S+\s+)*?clean\b",
    r"\bgit\s+(\S+\s+)*?rebase\b",
    r"rm\s+.*(-[rf].*-[rf]|-[rf]{2,}|--recursive.*--force|--force.*--recursive)",
    r"find\s+.*(-delete|-exec|-execdir)",
]

tool_input = json.loads(sys.stdin.read())
cmd = tool_input.get("tool_input", {}).get("command", "")

if not cmd:
    sys.exit(0)

for pattern in DANGEROUS_PATTERNS:
    if re.search(pattern, cmd):
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": f"Matches dangerous pattern: {pattern}",
                }
            },
            sys.stdout,
        )
        sys.exit(0)
