# Work Mac: Out-of-Git Files

This documents private files that live **only** on the work Mac, plus their tracked consumers. Private files are maintained manually. Work reconciles through native mise alone, like every other host.

Every private input is gitignored before it holds corporate values. `*.local.toml` files and `bootstrap/targets/*/local/` directories are ignored repo-wide; `.fdignore` unhides them for `fd` and the editor file picker.

## Target Variables

Git/Jujutsu identity, corporate Git URL rewrites, LazyGit services, Go editor settings, Neovim private values, and Python indexes belong in `bootstrap/targets/ML-DFC6YK6VJQ/mise.local.toml`. Mise loads it for every capability environment of the target.

## Agent Configuration

The untracked `bootstrap/capabilities/agent-harness/local/ML-DFC6YK6VJQ/` holds the work agent inputs:

| File                           | Consumed by                                                           |
| ------------------------------ | --------------------------------------------------------------------- |
| `data.toml`                    | Native agent configuration (models, gateway, footer, MCP)             |
| `catalogue.toml`               | Native agent catalogue: private sources appended after the shared one |
| `claude-settings-overlay.json` | Claude settings overlay                                               |
| `statusline-usage.sh`          | Claude statusline usage section                                       |
| `assets.toml` and its sources  | Work-only linked assets such as Claude hooks                          |

`data.toml` fields:

| Field                | Consumed by                                            |
| -------------------- | ------------------------------------------------------ |
| `[work_models]`      | Pi models/settings, Claude Code overlay                |
| `[work_gateway]`     | Pi providers (endpoint and provider names)             |
| `inferenceBudgetUrl` | Native Pi renderer (`powerlineCustom.budget.url`)      |
| `costsDashboardUrl`  | Native Pi renderer (`powerlineCustom.budget.costsUrl`) |
| `jiraBrowseUrl`      | Pi footer settings                                     |
| `piWorkPackages`     | Pi packages prepended to the work set                  |
| `[[mcp_servers]]`    | Claude MCP registration                                |
| `pi_mcp_json`        | Native Pi renderer (`~/.pi/agent/mcp.json`)            |

Keep credentials out of these files. `ANTHROPIC_AUTH_TOKEN` remains a SecretRef in `fnox.work.toml`, and `mise agent-config` resolves it only for rendering private mode-0600 outputs. Run `mise agent-config --check` first, then `mise agent-config --check --real-secrets` to prove credential access without writing.

`catalogue.toml` uses the shared catalogue's `[[sources]]` schema. Sources are appended after the tracked catalogue and resolved for the `work` profile:

```toml
[[sources]]
repo = "https://scm.example/scm/ai/plugin.git"

[[sources.plugins]]
name = "my-plugin"
include_skills = []

[[sources]]
local = "/Users/me/code/local-plugin"

[[sources.plugins]]
name = "another-plugin"

[sources.plugins.skills]
deployed-name = "skills/some-skill"
```

The work host declaration is `bootstrap/targets/ML-DFC6YK6VJQ/mise.agent-harness.toml`; it enables Claude and Pi only and records ownership in `~/.cache/ansiblonomicon-harness/work-managed-files.json`.

## Shell Extras

The shared startup files are owned by the native mise shell capability. They source `~/.zshenv.local` and `~/.zshrc.local`, which the ignored `bootstrap/targets/ML-DFC6YK6VJQ/mise.shell-work.local.toml` declares from `bootstrap/targets/ML-DFC6YK6VJQ/local/shell/`: the environment file is copied privately at mode 0600, the interactive file is linked. `SOURCEGRAPH_TOKEN` is the shell-wide exception because its plugin requires inheritance and Pi may launch non-interactively. The shell task resolves that value and its scoped sudo credential through `fnox-host` before rendering the private mode-0600 `.zshenv`; it does not perform a startup-time network read. Command-specific credentials continue to use `scripts/fnox-host exec --secret NAME [--secret NAME ...] -- COMMAND`. Do not restore broad provider-token exports or global agent launch wrappers.

## Work-Local Machine Tasks

`mise work-local` applies the ignored `bootstrap/targets/ML-DFC6YK6VJQ/mise.work-local.local.toml`, with sources in `bootstrap/targets/ML-DFC6YK6VJQ/local/work-local/`. Full laptop reconciliation runs it after the other configuration capabilities. It holds machine automation that must not live in git, such as privileged LaunchDaemons and user LaunchAgents mise cannot declare natively. Its final hook reloads each job only when the job is missing or its plist digest changed.

## Claude Code

- `bootstrap/capabilities/agent-harness/local/ML-DFC6YK6VJQ/claude-settings-overlay.json`
  supplies the work-only settings overlay.
- `bootstrap/capabilities/agent-harness/local/ML-DFC6YK6VJQ/assets.toml`
  declares work-only assets. Sources are relative to that same host-local directory;
  destinations are HOME-relative and `mode` must be `symlink`:

### Merge Semantics

The native Claude renderer:

1. Deep-merges the work overlay onto the tracked base
2. Aggregates hook fragments from `~/.cache/ansiblonomicon-harness/hooks/*.json` into the hooks section

Rules:

- Object fields are recursively merged (overlay keys win)
- Scalar/array fields in the overlay **replace** the base
- Fields set to `null` are **removed** from the final output

Note: The `permissions.allow` array in the overlay **replaces** the base entirely (array merge is not recursive). The base defines personal permissions; the work overlay provides the full work set.

### Model Configuration

The native host-local `data.toml` defines models under `[work_models]`, one entry per model the gateway serves: `version` (the bare id), `pi_alias` (the `provider/id` pair pi resolves by, mirroring `agent_harness.aliases.pi` in `bootstrap/capabilities/agent-harness/models.yml`), `display_name`, `context_window`, `max_output`, and the negotiated `cost` rates.

`[work_gateway]` holds the endpoint and the two pi provider names. One gateway fronts two wire protocols — Anthropic Messages and OpenAI Responses (at `{base_url}/v1`) — so Pi needs a provider per protocol. Both authenticate with `ANTHROPIC_AUTH_TOKEN`, resolved through fnox by the native agent configuration renderer or supplied to the agent by `scripts/fnox-host exec --secret ANTHROPIC_AUTH_TOKEN -- COMMAND`.

These should be used instead of hard-coding model values.

## Homebrew

| File                                                  | Purpose                                                 |
| ----------------------------------------------------- | ------------------------------------------------------- |
| `bootstrap/capabilities/mac-apps/Brewfile.work`       | Work-specific brews, casks, and taps (committed to git) |
| `bootstrap/capabilities/mac-apps/Brewfile.work.local` | Machine-local additions not committed to git            |

`Brewfile.work` includes every sibling `Brewfile.work.*`; the `.local` variant is for corporate taps and tools that are not publicly available.

## Work-Local Config

| File                                                        | Purpose                                                     |
| ----------------------------------------------------------- | ----------------------------------------------------------- |
| `bootstrap/targets/ML-DFC6YK6VJQ/language-tools.local.toml` | Native private language-tool additions                      |
| `mise.local.toml`                                           | Work-only exclusions for project tools supplied by Homebrew |

`mise.local.toml` disables `markdownlint-cli2` and `npm:mcp-remote`; Homebrew supplies both because Artifactory lacks the required npm releases. `language-tools.local.toml` is required before `language-tools` runs; an empty file explicitly confirms there are no private extras. The native task validates this inventory and applies the private Python-index configuration before running package managers.

```toml
[tools.ruby]
version = "latest"

[npm]
packages = ["private-cli"]
allow_scripts = []

[uv]
packages = ["some-private-tool"]

[go]
packages = ["gitlab.internal/org/tool"]
```

The tracked `tools.work.toml` links Pi's Glimpse clone into the global npm root through `[npm.links]`, because the registry lacks `glimpseui`. The link is restored after every Node change.

## Agent Harness Local Plugin

| File           | Purpose                                           |
| -------------- | ------------------------------------------------- |
| `agents/work/` | Gitignored local plugin with work-specific skills |

Declared for the `work` profile in `bootstrap/capabilities/agent-harness/catalogue.toml`.

## Local Agent Instructions

| File                | Purpose                                                        |
| ------------------- | -------------------------------------------------------------- |
| `./AGENTS.local.md` | Work-machine instructions loaded alongside the project context |

## MCP Servers

Native agent configuration reads `[[mcp_servers]]` from the host-local `data.toml` and registers Claude user-scope servers. Repo-local skills can only launch subprocess MCP servers, so the Cloudflare skill uses Homebrew's `mcp-remote` to translate stdio MCP traffic to Cloudflare's authenticated HTTP endpoint. Pi and Claude's static project config support HTTP directly and bypass the adapter.

## Python Package Indexes (uv + pip)

| File                     | Purpose                                                              |
| ------------------------ | -------------------------------------------------------------------- |
| Target `mise.local.toml` | Native system-level uv and pip indexes (`python_index_config`)       |
| `./uv.toml`              | Project-level override for this repo (gitignored, non-CICD endpoint) |

Work reconciliation and focused checks fail before writing either target when `python_index_config` is absent or invalid. Personal and pod042 hosts intentionally leave both files absent.

### uv.lock handling

`uv sync` rewrites `uv.lock` with mirror URLs. To prevent committing these:

- `mise run bootstrap` sets `skip-worktree` on `uv.lock` and the pi extensions `package-lock.json` — git ignores local changes, `git add` silently skips them
- **Use `mise run pull` instead of `git pull`** — lifts both masks, restores the canonical lockfiles, rebases, re-resolves the work-local lock against Artifactory, re-syncs, and re-masks
- Dependency updates must be committed from a personal machine (where the lock resolves against `pypi.org`)

#### Mirror lag and wheel-only resolution

The work `mise run pull` re-resolves the masked lock with `uv lock --no-build --upgrade`, not a plain `uv sync`. This allows for differences in sources across machines, including mixups with source dist and wheels for different os's. A version-only resolve would pin that release and then fail trying to build it from source. `--no-build` forbids the source fallback, while `--upgrade` prevents the canonical lock from keeping an incompatible release pinned, so resolution backs off to the newest version the mirror serves as an installable wheel.

This only bites when the lock targets a single platform — with the canonical multi-platform lock, another platform's wheel keeps the unbuildable version pinned. So `mise run pull` transiently injects single-platform `[tool.uv] environments` and `required-environments` restrictions, runs the wheel-only resolve, then restores `pyproject.toml` from a backup before syncing. The restrictions are never committed, so no mirror version details leak to git, and the canonical `pyproject.toml` stays platform-agnostic.

The mechanism is generic (no per-package pins, no version numbers anywhere) and self-heals: once the mirror carries the macOS-arm64 wheel, the work lock picks up the newer version automatically. A personal machine resolves the same `pyproject.toml` against `pypi.org`, where the wheel exists, so it floats to the latest. "Latest" thus differs per machine by what each index actually serves.

The restriction also pins `python_version` to the interpreter running the pull. Without it, the open `requires-python = ">=3.14"` makes uv resolve a Python 3.15+ split as well, and the mirror serves no wheels for that yet, so every compiled dependency (`markupsafe`, `pyyaml`) fails the wheel-only resolve.

### pi extension package-lock.json handling

The pi extensions `package-lock.json` (`bootstrap/capabilities/agent-harness/configuration/assets/pi/extensions/`) has the same mirror-URL problem: `npm install` on work rewrites it with Artifactory URLs. `mise run bootstrap` sets `skip-worktree` on it (gated by hostname) so the rewrite never reaches git, and `mise run pull` lifts/re-applies the mask around the rebase (see above). Dependency/lock bumps for pi extensions must be committed from a personal machine, where it resolves against the public npm registry.

## Setup Checklist

When setting up a new work Mac, copy these files from the old machine:

- `bootstrap/targets/ML-DFC6YK6VJQ/mise.local.toml`
- `bootstrap/targets/ML-DFC6YK6VJQ/mise.*.local.toml` and `bootstrap/targets/ML-DFC6YK6VJQ/local/`
- `bootstrap/targets/ML-DFC6YK6VJQ/language-tools.local.toml`
- `bootstrap/capabilities/agent-harness/local/ML-DFC6YK6VJQ/`
- `bootstrap/capabilities/mac-apps/Brewfile.work.local`
- `mise.local.toml`
- `agents/work/`
- `./AGENTS.local.md`
- `./uv.toml`

Run `mise laptop --check` before `mise laptop`.
