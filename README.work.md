# Work Mac: Out-of-Git Files

This documents all files that live **only** on the work Mac and are not tracked in this repository. These are maintained manually.

## Chezmoi Data Layer

| File                                             | Purpose                                                                                        |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `~/.local/share/chezmoi/.chezmoidata/local.toml` | Git identity, SCM hosts (as `[[scm]]` array), Go import/build config, Claude Code model config |

Defaults for `goLocalImports` and `goplsBuildFlags` are declared in `.chezmoidata.toml` (empty strings). `scm` defaults to an empty array.

## Shell Extras

| File              | Purpose                                                     |
| ----------------- | ----------------------------------------------------------- |
| `~/.zshenv.local` | Corporate env vars, proxy config, auth tokens sourced early |
| `~/.zshrc.local`  | Interactive shell extras (corporate tool init, completions) |

These are sourced by the chezmoi-managed `.zshenv.tmpl` and `.zshrc.tmpl` if they exist.

## Claude Code

| File                                                           | Purpose                                                        |
| -------------------------------------------------------------- | -------------------------------------------------------------- |
| `chezmoi/.chezmoitemplates/local/claude-settings-overlay.json` | Work-machine overrides merged onto base during `chezmoi apply` |
| `chezmoi/.chezmoitemplates/local/resolve-overlay.py`           | Script that merges overlay with base                           |

### Merge Semantics

The chezmoi template `dot_claude/settings.json.tmpl` calls `resolve-overlay.py` which:

1. Deep-merges the work overlay (`.chezmoitemplates/local/claude-settings-overlay.json`) onto the base if the overlay exists
2. Aggregates hook fragments from `~/.cache/ansiblonomicon-harness/hooks/*.json` into the hooks section

Rules:

- Object fields are recursively merged (overlay keys win)
- Scalar/array fields in the overlay **replace** the base
- Fields set to `null` are **removed** from the final output

Note: The `permissions.allow` array in the overlay **replaces** the base entirely (array merge is not recursive). The base defines personal permissions; the work overlay provides the full work set.

### Model Configuration

`local.toml` defines Claude Code model IDs under `[claude_code_models]`:

These should be used instead of hard-coding model values.

## Homebrew

| File                          | Purpose                                                  |
| ----------------------------- | -------------------------------------------------------- |
| `ansible/Brewfile.work`       | Work-specific brews, casks, and taps (committed to git)  |
| `ansible/Brewfile.work.local` | Machine-local additions not committed to git (if needed) |

`Brewfile.work` **is** committed. The `.local` variant is for tools that are not publicly available.

## Agent Harness Sources

| File                             | Purpose                                                       |
| -------------------------------- | ------------------------------------------------------------- |
| `ansible/sources.work.local.yml` | Work-specific plugin git sources (internal repos, gitignored) |

The work playbook conditionally includes this file if it exists. It defines `agent_harness_sources_extra` which gets appended to `agent_harness_sources_base` (defined in `work.config.yml`).

Structure:

```yaml
---
agent_harness_sources_extra:
  - repo: https://scm.internal/scm/proj/plugin-marketplace.git
    pull: true
    plugins:
      - name: my-plugin
      - name: another-plugin
```

The `repo` field accepts full git URLs (ending in `.git`) or the short `owner/name` form (auto-expanded to GitHub). Use `exclude_skills` on any plugin entry to skip specific skills.

## Agent Harness Local Plugin

| File           | Purpose                                           |
| -------------- | ------------------------------------------------- |
| `agents/work/` | Gitignored local plugin with work-specific skills |

Added to `agent_harness_sources_base` in `work.config.yml`.

## MCP Servers

| File                                             | Purpose                                                   |
| ------------------------------------------------ | --------------------------------------------------------- |
| `~/.local/share/chezmoi/.chezmoidata/local.toml` | `[[mcp_servers]]` entries for user-scope MCP registration |

The chezmoi `run_onchange_after_register-mcp-servers.sh` script reads `[[mcp_servers]]` from `local.toml` and runs `claude mcp add --scope user` for each entry. Supports `transport = "http"` (URL-based) and `transport = "stdio"` (command + args).

## Python Package Indexes (uv + pip)

| File                                             | Purpose                                                                                                     |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| `~/.local/share/chezmoi/.chezmoidata/local.toml` | System-level indexes (`pypiIndex`, `uvIndexStrategy`) → `~/.config/uv/uv.toml` and `~/.config/pip/pip.conf` |
| `./uv.toml`                                      | Project-level override for this repo (gitignored, non-CICD endpoint)                                        |

Both `uv.toml` and `pip.conf` are rendered from the same `pypiIndex` data in `local.toml`. The default index becomes `global.index-url` in pip; non-default entries become `extra-index-url`. System-level config defaults to CICD Artifactory (correct for most work projects). This repo overrides to the enterprise endpoint since it's a personal repo not deployed through CICD.

### uv.lock handling

`uv sync` rewrites `uv.lock` with mirror URLs. To prevent committing these:

- `.envrc` sets `skip-worktree` on `uv.lock` — git ignores local changes, `git add` silently skips it
- **Use `poe pull` instead of `git pull`** — lifts the mask, restores the canonical lock, pulls, re-syncs, and re-masks
- Dependency updates must be committed from a personal machine (where the lock resolves against `pypi.org`)

## Ansible Local Tasks

| File                           | Purpose                                                                                             |
| ------------------------------ | --------------------------------------------------------------------------------------------------- |
| `ansible/tasks/work.local.yml` | Machine-local Ansible tasks included by `work.yml` (gitignored, runs via `poe laptop --tags local`) |

The work playbook conditionally includes this file if it exists. Place any work-specific automation here that shouldn't live in git.

Currently deploys a LaunchAgent to manage claude model versions.

## fd / File Picker Visibility

`.fdignore` at repo root uses negation patterns (`!path`) to unhide work-only files from `fd` (and LazyVim's file picker) despite them being in `.gitignore`. When adding a new gitignored work file, add a corresponding `!` entry to `.fdignore`.

## Prettier Formatting

Prettier skips gitignored paths by default. The project-local `.nvim.lua` (`exrc`) tells conform to pass `--ignore-path .prettierignore` to prettier, making it read _only_ that file instead of `.gitignore`. This means all files — including gitignored work-only paths — get formatted on save.

`.prettierignore` exists as an empty file to satisfy the `--ignore-path` flag. Add explicit exclusions there only if a file should never be formatted.

## Setup Checklist

When setting up a new work Mac, copy these files from the old machine:

- `~/.local/share/chezmoi/.chezmoidata/local.toml`
- `~/.zshenv.local`
- `~/.zshrc.local`
- `chezmoi/.chezmoitemplates/local/claude-settings-overlay.json`
- `ansible/sources.work.local.yml`
- `ansible/tasks/work.local.yml`
- `agents/work/`
- `./uv.toml`

Then run `chezmoi apply` and `uv run poe laptop`.
