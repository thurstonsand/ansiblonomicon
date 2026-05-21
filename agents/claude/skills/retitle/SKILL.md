---
name: retitle
description: Regenerate the session title from current conversation context
argument-hint: "[direction for the title]"
disable-model-invocation: true
allowed-tools: Bash(python3 *retitle.py *)
---

# Retitle

Respond to the user with only: "Title updated: !`python3 ~/.claude/hooks/retitle.py "${CLAUDE_SESSION_ID}" "$ARGUMENTS" 2>&1`". If the output indicates an error, relay the error instead. Nothing else.
