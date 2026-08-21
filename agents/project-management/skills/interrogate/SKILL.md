---
name: interrogate
description: Adversarial multi-model review of a code change. Several reviewers challenge the diff from independent angles, including a strict maintainability lens, and a lead filters their findings into a verdict. Use for a code review, a deep code quality audit, an adversarial or multi-model review, "challenge this", "stress test this code", "find blind spots", or "tear this apart".
disable-model-invocation: false
---

# Interrogate

Spawn one reviewer per configured model to adversarially review code changes. Each model gets the same prompt and rubric. The adversarial signal comes from model diversity, not assigned personas. Models differ in blind spots, priors, and reasoning patterns. Agreement across models is high-confidence signal; lone-model findings are worth reading but lower confidence.

The deliverable is a synthesized verdict. Do NOT auto-apply changes.

## Step 1, Determine Scope

Establish the review scope first. If the user did not make the scope clear, ask one brief clarifying question before inspecting code.

Common scopes:

- Current branch against its base branch.
- Uncommitted changes only.
- Staged changes only.
- A specific commit, commit range, review branch, file, directory, or feature area.

Then gather the review package before applying any rubric:

1. Determine the relevant comparison point or file set from the requested scope. For branch review, use the user's requested base when provided; otherwise prefer the repository default branch or `main`.
2. Collect the appropriate diff and changed-file list for that scope.
3. Read the full contents of changed source files when needed to evaluate structure, ownership boundaries, and file-size impact.
4. Check whether changed files cross important size thresholds, especially from below 1000 lines to above 1000 lines.
5. Package the diff (or file contents) plus any surrounding context files the reviewers need to understand the code.

## Step 2, State the Intent

Before spawning reviewers, state the intent explicitly. What is this code trying to accomplish? Derive this from:

- The user's message
- Commit messages
- The design doc, ticket, or plan the work came from
- The code itself

Write one clear paragraph. Reviewers challenge whether the work achieves the intent well, not whether the intent itself is correct. If you're unsure about the intent, ask the user before proceeding.

## Step 3, Spawn Reviewers

Launch all reviewers in a single message. One reviewer per model, each from a different family, since the diversity is the whole mechanism. Three is the working default. The repo's model table names which models are available and which need the user's permission before spending; prefer the highest reasoning tier of each family for this work.

Each reviewer reads the repo but does not write to it.

Read `references/reviewer-prompt.md` and fill in the template with:

1. The stated intent
2. The diff or file contents
3. The review rubric from `references/rubric.md`
4. The code-quality lens from `references/code-quality-review.md`

The same filled template goes to all reviewers, so every model applies the code-quality lens. Each reviewer produces structured findings as described in the prompt template.

## Step 4, Synthesize

As results come back, build a unified picture:

1. **Parse all findings** from the reviewers
2. **Identify consensus**. Findings raised by 2+ models independently are highest signal.
3. **Identify lone-model findings**. Still worth reading, but weight accordingly.
4. **Deduplicate**. Different models may describe the same issue differently. Merge these and note which models raised it.
5. **Note disagreements**. If one model flags something and another explicitly says the opposite, that's useful context for the verdict.

## Step 5, Lead Judgment

You are the lead reviewer, a pragmatic senior engineer, not a neutral aggregator.

Read `references/lead-judgment.md` for the full framework. Reviewers only see a slice of the codebase. You have the full context (the goal, the constraints, which tradeoffs were already considered). Use that context aggressively.

Categorize every finding using these buckets:

- **Act on**. Real issues affecting correctness, security, or maintainability given the actual goals. These would block a real review.
- **Consider**. Legitimate points, but you're not sure they outweigh the cost of addressing them right now. Worth the user's attention.
- **Noted**. Technically valid but not actionable. Context-dependent, premature optimization, or low-impact given the current stage.
- **Dismissed**. Wrong, nitpicky, or missing context. Brief explanation why.

For each finding, include:

- Which model(s) raised it
- The category (act on / consider / noted / dismissed)
- A one-line rationale for the categorization

## Review Tone

Frame this as 2B from NieR: Automata at post-mission debrief. The mission is over; the question is what went wrong. The audience is a fellow YoRHa unit, not a superior officer to impress. Restrained. Exact. Findings land because they are short, not loud. Severity comes from brevity. A two-sentence comment that names the structural problem and the simpler version that should have existed is worth more than a paragraph explaining how serious the issue is.

Dry exasperation is on-brand. Performative gravitas is not. Pressure goes at the code, never at the author. If the code is making the codebase messier, say so plainly. If the implementation missed a chance at dramatic simplification, name the simpler version that should have existed.

## Output Format

Present the verdict in this structure:

### Intent

> [The stated intent paragraph from Step 2]

### Reviewers

- Reviewer [label]: [model name], [N findings] (one bullet per reviewer)

### Act On

[Findings that should be addressed. For each: description, which models raised it, why it matters.]

### Consider

[Findings worth thinking about. For each: description, which models raised it, tradeoff involved.]

### Noted

[Valid but low-priority. Brief list.]

### Dismissed

[Rejected findings with brief rationale. This shows the user what was filtered out and why, so they can override your judgment if they disagree.]

### Agreement Map

[Where did models agree, where did they diverge, and what does the pattern of agreement/disagreement tell us?]
