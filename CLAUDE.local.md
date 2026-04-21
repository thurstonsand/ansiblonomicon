# CLAUDE.local.md (work machine)

## Git Pull

Use `poe pull` instead of `git pull`. On this machine, `uv.lock` is masked via `skip-worktree` because `uv sync` rewrites it with internal mirror URLs. Raw `git pull` will fail when upstream changes `uv.lock`. `poe pull` handles the mask/unmask cycle transparently.

Also avoid `git merge`, `git rebase`, `git stash pop` when `uv.lock` is involved upstream — same skip-worktree issue. When in doubt, use the same dance: lift the mask, checkout the lock, do the operation, re-sync, re-mask.
