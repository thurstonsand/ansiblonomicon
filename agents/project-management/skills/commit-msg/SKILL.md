---
name: commit-msg
description: Generate descriptive commit messages by analyzing git diffs. Use when the user asks for help commiting code, writing commit messages, or reviewing staged changes.
---

# Git Commit Helper

## Purpose

Commit messages are trust artifacts. A well-written commit should give the reader enough context to decide whether they need to review the code at all. Capture intent, decisions, and verification — not just what files changed.

## Gather Context

Before drafting the message, collect:

```bash
# What's staged
git diff --staged --stat
git diff --staged

# Recent commits for tone and convention
git log --oneline -5
```

Read the diff carefully. Understand *why* the change was made, not just what changed. If you made the changes yourself, you already have this context — use it.

## Commit Message Format

```
<type>(<scope>): <summary>

Why: <problem solved or request fulfilled>
Approach: <what was done and key decisions made>
Verified: <how correctness was confirmed>

[Tradeoffs: <alternatives considered, things intentionally left out>]
[Breaking: <what breaks and migration path>]
```

### The Header

Follow conventional commits. Keep the summary under 50 characters, imperative mood.

**Types:** feat, fix, docs, style, refactor, test, chore

### Why

One or two sentences explaining the motivation. What was broken, missing, or requested? This should make sense to someone who wasn't in the conversation where the work was discussed.

### Approach

What you did and, critically, *why you did it that way*. Include:

- Design decisions that weren't obvious
- Patterns chosen and why (especially if the codebase has multiple precedents)
- Scope boundaries — what you intentionally didn't change

This is where agent context gets preserved. If you chose approach A over approach B, say so. That reasoning exists in your working memory right now and will be lost after the session ends.

### Verified

How you know the change is correct. Be specific:

- "Added 3 unit tests covering the new parsing logic, all passing"
- "Ran the full test suite (142 tests), no regressions"
- "Manually tested the endpoint with curl, confirmed 200 response with expected payload"
- "Type-checked with tsc --noEmit, no errors"

If verification was limited, say that too: "No existing test suite — verified by running the script against sample input." Honest verification is more useful than vague confidence.

### Tradeoffs (optional)

Include when you made a deliberate choice between reasonable alternatives. Skip for straightforward changes where there was one obvious path.

### Breaking (optional)

If the change breaks existing behavior, state what breaks and how to migrate. Use the `!` suffix in the header too: `feat(api)!: restructure response format`

## Proportionality

Match message depth to change significance. A dependency bump doesn't need a Tradeoffs section. A major architectural change deserves every section plus maybe an ADR. Use judgment.

## Creating the Commit

```bash
git commit -m "<header>" -m "<body>"
```

For longer messages, prefer writing to a temp file:

```bash
cat > /tmp/commit-msg.txt << 'EOF'
<full message>
EOF
git commit -F /tmp/commit-msg.txt
```

## Checklist

Before committing:

- [ ] Header follows conventional commits format
- [ ] Why section explains motivation, not just mechanics
- [ ] Approach captures decisions that would otherwise be lost
- [ ] Verified section is specific about what was tested and what passed
- [ ] Message is proportional to the change size
- [ ] Read the message as if you're seeing it in 6 months — does it make sense?
