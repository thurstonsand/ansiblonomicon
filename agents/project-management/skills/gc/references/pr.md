# PR Review Helper

## Overview

Create pull requests with an interactive review workflow that allows users to edit the PR description before submission. Analyze the complete change since the branch diverged, then describe its final state concisely.

## Workflow

Follow these steps sequentially when creating a pull request:

### 1. Gather Git Context

Collect all necessary git information to understand the full scope of changes:

- Base branch, using the user's requested base, the existing PR's base, or the repository's default branch
- Current git status: `git status`
- All changes since diverging from the base: `git diff <base>...HEAD`
- Current branch name: `git branch --show-current`
- All commits on this branch: `git log <base>..HEAD`
- Remote tracking status: `git status -b --porcelain | head -1`
- Check if current branch tracks a remote: `git rev-parse --abbrev-ref @{upstream} 2>/dev/null || echo "No upstream tracking"`

Execute these commands in parallel for efficiency.

### 2. Analyze Changes and Draft PR Description

Based on the gathered context:

- Analyze ALL commits that will be included in the pull request (not just the latest commit)
- Review the full diff to understand the complete scope of changes
- Draft a concise title and body focused on the final aggregate change
- Use bullet points for prose; use code snippets, diagrams, or code references when they explain the change more clearly
- Omit intermediate details that do not survive in the final diff, such as an earlier implementation's size or refactoring between commits
- For a difficult, high-risk, or wide-scoped change, use a longer technical narrative when context, before-and-after examples, or design reasoning will materially help reviewers

### 3. Present Description for Review

Present the draft title and description to the user for easy copying and editing:

**Title:** `<Clear, descriptive title>`

```markdown
## Summary

- <Main change point 1>
- <Main change point 2>
- <Main change point 3>
```

- Keep the default body brief. Do not write an essay or include routine statements that tests were run.
- Include a short validation section only when the repository's PR template requires it or the evidence materially helps reviewers assess risk.
- For visual changes, add a before-and-after table containing uploaded images or videos.
- For benchmarks, add a table comparing the target-branch baseline with the pull request candidate.
- Ask the user to review and suggest any edits before creating the PR.
- Write each bullet or paragraph as a single soft-wrapped line, and do not insert hard newlines to wrap text within a point.

### 4. Wait for User Approval

After presenting the description, explicitly wait for the user to indicate they have reviewed and approved the description. Do not proceed to creating the PR until the user confirms they are ready.

### 5. Create the Pull Request

Once the user approves, create the pull request or merge request using the repository host's CLI or API. For GitHub:

```bash
# Ensure current branch is pushed to remote with upstream tracking if needed
git push -u origin $(git branch --show-current)

# Create the PR
gh pr create --title "<title>" --body-file <body-file> --base <base>
```

Return the PR URL to the user.

## Important Notes

- Always analyze ALL commits in the branch, not just the most recent one
- The PR description should reflect the final aggregate change since diverging from the base branch
- Never skip the user review step - this is a critical part of the workflow
- If the user provides additional notes or context as arguments, incorporate them into the PR description
