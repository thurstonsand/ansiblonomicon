---
name: showboat
description: Build proof-of-work documents that mix commentary, executable code blocks, and captured output to demo what you built. Use when asked to "demo", "show what you've built", or "prove that it works".
---

# Showboat

Run `showboat --help` to see the full usage reference.

## Quoting

Be careful with `showboat exec ... bash ...` when the shell snippet contains `$vars`, `$(command substitutions)`, or heredocs.

- If you wrap the code argument in double quotes, your current shell expands it before `showboat` records or executes it.
- Prefer single quotes around the code argument when possible.
- If the snippet itself needs heavy quoting, pipe it on stdin instead of passing it as a single shell argument.
