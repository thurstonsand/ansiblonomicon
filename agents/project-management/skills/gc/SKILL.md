---
name: gc
description: Review local docs and create a git commit. Use when the user wants to commit changes with proper documentation review.
---

# Git Commit with Documentation Review

A composite workflow that ensures documentation is up-to-date before committing changes.

## Workflow

Execute these steps in order:

### 1. Review Documentation

Load and follow the `updating-documentation-for-changes` skill to review all relevant documentation for the staged changes.

### 2. Stage Documentation Updates

After reviewing and updating documentation:

```bash
git add <updated-docs-only>
```

**Important:** Only stage documentation files that were actually modified. Do not blindly `git add .` as there may be unstaged files not ready for commit.

### 3. Create the Commit

Load and follow the `git-commit-helper` skill to generate an appropriate commit message and create the commit.

## When to Use

- After making code changes that may affect documentation
- Before creating a pull request
- When you want a thorough commit workflow with documentation checks
