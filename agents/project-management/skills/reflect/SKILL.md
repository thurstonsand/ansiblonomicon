---
name: reflect
description: Spawn three parallel review subagents over the active transcript, surface learnings, and route each to a concrete edit on an existing skill. Use when the user says reflect.
disable-model-invocation: true
---

# Reflect

Mine the current conversation for durable learnings, then route them into skill edits.

## When to invoke

- The user said "reflect" or "/reflect".
- A complex task (5+ tool calls) just landed cleanly and the recipe is worth keeping.
- The agent hit dead ends, found the working path, and the path generalizes.
- The user corrected the agent's approach mid-task.
- A non-trivial workflow emerged that isn't captured anywhere.

Skip when the conversation is trivial, off-topic, or already covered by an existing skill the parent followed correctly. One-offs are not learnings.

## Process

### 1. Locate the active transcript

The parent finds its own transcript before fanning out. Every harness stores sessions differently, so resolve the path from this session's own environment rather than guessing at a layout, and stay inside the current project's session directory. Globbing across every project crosses workspace boundaries and reads private conversations from unrelated work.

If the harness exposes its own tools for searching and reading sessions, prefer those over a raw file path, and hand the reviewers the session identifier instead. If nothing resolves, write a tight digest of the session and pass that instead.

### 2. Spawn three reviewers in parallel

One message, three subagents, one per lens. Each runs on a different model, since the point is the blind spots you cannot bring yourself. Reviewers need to read the repo and look up context; the prompt forbids file writes, and the parent applies edits.

| Lens | Model | Prompt template |
|---|---|---|
| Judgment | the strongest judgment model | `references/judgment-reviewer.md` |
| Tooling | the strongest instruction-following model | `references/tooling-reviewer.md` |
| Divergent | a judgment model from a different family than the parent | `references/divergent-reviewer.md` |

The repo's own model table names which model currently fills each role, including any that need the user's permission before spending. Pass each template verbatim, substituting the transcript path, session identifier, or digest where marked. Reviewers return findings in their response body.

### 3. Synthesize

One subagent on the judgment model. Use `references/synthesizer.md` verbatim, with each reviewer's full output inlined where marked. The synthesizer returns a structured Accepted / Rejected / Backlog list.

### 4. Structural enforcement check

Sanity-check the synthesizer's Accepted list. For any item that a lint rule, script, permission rule, metadata flag, or runtime check would enforce more reliably, move it from Accepted to Backlog. A rule you can enforce mechanically has no business being prose in a skill. The synthesizer already applies this criterion; this is a final pass before edits land.

### 5. Apply

Before applying any Accepted edit, present the synthesizer's full Accepted / Rejected / Backlog output to the user and wait for explicit approval. The user picks which subset to apply and may redirect routings. Skill changes reach every future agent on every machine; do not auto-apply.

Reviewers cite the skill path they saw, which is the deployed copy. Edits land on the source skill in this repo, never on the deployed copy, which is overwritten on the next reconcile.

Backlog items are reported, not filed. Only the Accepted list waits for approval.

For each approved Accepted item, follow the Routing field exactly:

- Trivial existing-skill edit (a one-line bullet, a tightened sentence, a stale fact corrected): parent does directly.
- Substantive existing-skill edit (a new section, a new pattern table, more than ~10 lines): hand to the `writing-for-agents` skill and follow its guidance.
- `tune description: <skill path>` (the skill exists but didn't trigger when it should have): hand to `writing-for-agents` and rewrite the description around its triggers.
- `new skill via writing-for-agents: <kebab-name>`: hand creation to that skill. Do not invent the shape ad hoc.

If the repo ships a skill validator, run it on every touched skill before declaring done. Skip this step if it doesn't.

### 6. Summarize for the user

Short list, no preamble:

- Edits applied: `<skill path>`. What changed, one line each.
- New skills created: `<skill path>`. One line each (rare).
- Backlog: `<pattern>`, `<mechanism worth building>`. One line each.
- Dropped: one line per rejected finding + reason from the synthesizer.

Applied edits reach the machines on the next reconcile, not immediately.
