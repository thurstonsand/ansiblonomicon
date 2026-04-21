---
name: gc
description: Review local docs and create a git commit. Use when the user wants to commit changes with proper documentation review.
---

# Git Commit with Documentation Review

A composite workflow that ensures documentation is up-to-date before committing changes. You MUST invoke each skill as instructed.

## Workflow

Execute these steps in order:

### 1. Review Documentation

- Load the `updating-documentation-for-changes` skill
- Review all relevant documentation for the staged changes per the skill

### 2. Stage Documentation Updates

After reviewing and updating documentation:

```sh
git add <updated-docs-only>
```

**Important:** Only stage documentation files that were actually modified. Do not blindly `git add .` as there may be unstaged files not ready for commit.

### 3. Create the Commit

- Load the `git-commit-helper` skill
- Feel free to skip any steps already completed as part of step 1
- Generate an appropriate commit message per the skill and create the commit
