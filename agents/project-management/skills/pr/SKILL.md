---
name: pr
description: Creates pull requests with an interactive review and approval step. Use when asked to create a pull request, open a PR, or submit changes for review.
---

# PR Review Helper

## Overview

Create pull requests with an interactive review workflow that allows users to edit the PR description before submission. This skill analyzes all commits since diverging from the base branch and generates a comprehensive PR summary for user review.

## Workflow

Follow these steps sequentially when creating a pull request:

### 1. Gather Git Context

Collect all necessary git information to understand the full scope of changes:

- Current git status: `git status`
- All changes since diverging from main: `git diff main...HEAD`
- Current branch name: `git branch --show-current`
- All commits on this branch: `git log main..HEAD`
- Remote tracking status: `git status -b --porcelain | head -1`
- Check if current branch tracks a remote: `git rev-parse --abbrev-ref @{upstream} 2>/dev/null || echo "No upstream tracking"`

Execute these commands in parallel for efficiency.

### 2. Analyze Changes and Draft PR Description

Based on the gathered context:

- Analyze ALL commits that will be included in the pull request (not just the latest commit)
- Review the full diff to understand the complete scope of changes
- Draft a comprehensive PR summary using the format below

### 3. Present Description for Review

Present the draft PR description to the user in a code block for easy copying/editing:

```markdown
# <Clear, descriptive title>

## Summary

- <Main change point 1>
- <Main change point 2>
- <Main change point 3>

## Test plan

- [ ] <Test item 1>
- [ ] <Test item 2>
- [ ] <Test item 3>
```

Ask the user to review and suggest any edits before creating the PR.

### 4. Wait for User Approval

After presenting the description, explicitly wait for the user to indicate they have reviewed and approved the description. Do not proceed to creating the PR until the user confirms they are ready.

### 5. Create the Pull Request

Once the user approves, create the PR:

```bash
# Ensure current branch is pushed to remote with upstream tracking if needed
git push -u origin $(git branch --show-current)

# Create the PR
gh pr create --title "<title>" --body "<body>" --base main
```

Return the PR URL to the user.

## Important Notes

- Always analyze ALL commits in the branch, not just the most recent one
- The PR description should reflect the complete scope of changes since diverging from the base branch
- Never skip the user review step - this is a critical part of the workflow
- If the user provides additional notes or context as arguments, incorporate them into the PR description
