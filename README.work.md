# Work Mac: Out-of-Git Files

This documents all files that live **only** on the work Mac and are not tracked in this repository. These are maintained manually.

## Chezmoi Data Layer

| File                                             | Purpose                                                                     |
| ------------------------------------------------ | --------------------------------------------------------------------------- |
| `~/.local/share/chezmoi/.chezmoidata/local.toml` | Git identity, SCM hosts (as `[[scm]]` array), Go import/build configuration |

Defaults for `goLocalImports` and `goplsBuildFlags` are declared in `.chezmoidata.toml` (empty strings). `scm` defaults to an empty array. The work machine populates all keys in `local.toml` which chezmoi reads automatically but is gitignored.

## Shell Extras

| File              | Purpose                                                     |
| ----------------- | ----------------------------------------------------------- |
| `~/.zshenv.local` | Corporate env vars, proxy config, auth tokens sourced early |
| `~/.zshrc.local`  | Interactive shell extras (corporate tool init, completions) |

These are sourced by the chezmoi-managed `.zshenv.tmpl` and `.zshrc.tmpl` if they exist.

## Claude Code

| File                                                             | Purpose                                                         |
| ---------------------------------------------------------------- | --------------------------------------------------------------- |
| `~/.local/share/chezmoi/.chezmoidata/claude-settings.local.json` | Machine-local overrides merged onto base during `chezmoi apply` |

### Merge Semantics

The chezmoi template `dot_claude/settings.json.tmpl` deep-merges the overlay onto the base (`claude-settings.json`) using `jq` with `.chezmoitemplates/deepmerge.jq`. If the overlay file doesn't exist, the base is used as-is. Rules:

- Object fields are recursively merged (overlay keys win)
- Scalar/array fields in the overlay **replace** the base
- Fields set to `null` are **removed** from the final output

Note: The `permissions.allow` array in the overlay **replaces** the base entirely (array merge is not recursive). The base defines personal permissions; the work overlay provides the full work set.

## Homebrew

| File                          | Purpose                                                     |
| ----------------------------- | ----------------------------------------------------------- |
| `ansible/Brewfile.work`       | Work-specific brews, casks, and taps (committed to git)     |
| `ansible/Brewfile.work.local` | Machine-local additions not appropriate for git (if needed) |

`Brewfile.work` **is** committed. The `.local` variant is for tools that are not publicly available.

## Setup Checklist

When setting up a new work Mac:

1. Run `chezmoi init` with the repo
2. Create `~/.local/share/chezmoi/.chezmoidata/local.toml` with identity vars
3. Create `~/.zshenv.local` and `~/.zshrc.local` for corporate shell config
4. Create `~/.local/share/chezmoi/.chezmoidata/claude-settings.local.json` with machine-local overrides (env, permissions, sandbox, hooks, plugins)
5. Run `chezmoi apply`
6. Run `uv run poe work` from the repo
