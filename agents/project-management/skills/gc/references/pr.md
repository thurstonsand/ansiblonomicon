# PR Review Helper

## Overview

Create pull requests with an interactive review workflow that allows users to edit the PR description before submission. Analyze the complete change since the branch diverged, then describe its final state.

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

### 2. Draft the PR Description

Analyze ALL commits that will be included in the pull request, not just the latest, and describe the final aggregate change. Omit intermediate details that do not survive in the final diff.

Write the body following [pr-body.md](pr-body.md).

### 3. Present Description for Review

Present the draft title and body to the user for easy copying and editing. Write each bullet or paragraph as a single soft-wrapped line. Ask the user to review and suggest any edits before creating the PR.

### 4. Wait for User Approval

After presenting the description, explicitly wait for the user to indicate they have reviewed and approved the description. Do not proceed to creating the PR until the user confirms they are ready.

### 5. Create the Pull Request

Once the user approves, push the branch and create the pull request with the repository host's CLI or API. Return the PR URL to the user.

## Important Notes

- Never skip the user review step - this is a critical part of the workflow
- If the user provides additional notes or context as arguments, incorporate them into the PR description
