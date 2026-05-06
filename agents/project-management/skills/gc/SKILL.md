---
name: gc
description: Review local docs and create a git commit. Use when the user wants to commit changes with proper documentation review.
---

# Git Commit with Documentation Review

A composite workflow that ensures documentation is up-to-date before committing changes.

**CRITICAL:** This skill delegates to sub-skills. You MUST use the Skill tool to invoke each one — do NOT attempt to perform their work inline from memory or summary knowledge. The sub-skills contain detailed procedures that must be followed.

## Workflow

Execute these steps in order:

### 1. Review Documentation

Invoke the `updating-documentation-for-changes` skill and follow its instructions.

### 2. Stage Documentation Updates

After the documentation review skill completes, stage any documentation files that were modified:

```sh
git add <updated-docs-only>
```

Only stage documentation files that were actually modified. Do not `git add .` — there may be unstaged files not ready for commit.

### 3. Create the Commit

Invoke the `git-commit-helper` skill. Skip any steps (like reading the diff) already completed during step 1.
