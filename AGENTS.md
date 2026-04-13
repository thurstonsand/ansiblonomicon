# Skills

When working with TrueNAS (SSH, Docker containers, stacks, debugging services), **always load the `truenas-docker-ops` skill first**. It contains essential paths, commands, and helper scripts.

## Commands

- `./scripts/bootstrap.sh` — First-time setup on a brand new machine (installs Xcode CLI, Homebrew, Ansible, chezmoi, 1Password CLI)
  - `--ignore-certs` — Skip SSL verification for `ansible-galaxy install` (for corporate proxies)
- `./scripts/test-bootstrap.sh` — Test bootstrap in clean macOS VM via Tart
  - `--reuse` reuses existing VM; `--uninstall-xcode` tests fresh Xcode install; `--full-brew-bundle` uses real Brewfile
- `uv run poe macos` — Apply macOS Ansible playbook
  - `--check` / `-c` — Dry-run mode (no changes made)
  - `--tags` / `-t` — Only run tasks with specific tags (comma-separated)
  - **macOS tags**: `agent-harness`, `bun`, `chezmoi`/`dotfiles`, `claude-code`, `ghostty-nav`, `go`, `homebrew`/`mas`, `npm`, `opencode`, `ruby`, `sysconfig`/`hostname`, `terminal-theme`, `tmux`, `uv`, `uvc-util`
  - **macOS defaults tags**: `desktop-services`, `dock`, `finder`, `menubar`, `nsglobaldomain`, `permissions`
- `uv run poe work` — Apply work macOS Ansible playbook
  - **Work tags**: `ghostty-nav`, `homebrew`, `uvc-util`, `desktop-services`, `dock`, `finder`, `menubar`, `nsglobaldomain`, `permissions`
- `uv run poe truenas` — Apply TrueNAS Ansible playbook (same options as macos)
  - **TrueNAS tags**: `docker`/`docker-networks`, `docker-stack-role` (all stacks), or individual stacks: `anypod`, `arcane`, `arr-apps`, `caddy`, `cli-proxy-api`, `cloudflared`, `crabwalk`, `ddclient`, `ghost`, `homepage`, `isponsorblocktv`, `scrypted`, `torrent`
- `uv run poe udmp` — Apply UDMP Ansible playbook (same options as macos)
  - **UDMP tags**: `multicast-querier`, `nextdns`
- `uv run poe openclaw` — Apply OpenClaw Ansible playbook (run from openclaw itself)
  - `--check` / `-c` — Dry-run mode (no changes made)
  - `--tags` / `-t` — Only run tasks with specific tags (comma-separated)
  - **OpenClaw tags**: `agent-harness`, `apt`, `apt-repos`, `bun`, `cargo`, `chezmoi`/`dotfiles`, `claude-code`, `gateway-env`, `go`, `motd`, `neovim`, `npm`, `openclaw-monitors`/`monitors`, `openclaw-plugins`, `opencode`, `ruby`, `system-maintenance`/`timers`, `tmux`, `uv`, `xvfb`
- `uv run poe cz-diff` / `uv run poe cz-status` — Preview chezmoi changes (`cz-diff` excludes lockfiles)
- `uv run poe tfi` / `uv run poe tfp` / `uv run poe tfa` — Terraform init/plan/apply (Cloudflare infrastructure)
  - `--yes` / `-y` — Auto-approve apply (no confirmation prompt)
- `uv run poe pages-deploy` — Deploy Cloudflare Pages (tesla)
- `uv run poe wrangler` — Deploy all Workers (aig + hooks)
- `uv run poe wrangler:aig` — Deploy aig (AI Gateway proxy) Worker via Wrangler
  - `--force-secret` / `-f` — Update secrets even if they exist
- `uv run poe wrangler:hooks` — Deploy hooks (webhook gateway) Worker via Wrangler
  - `--force-secret` / `-f` — Update secrets even if they exist

## Dev Commands

- `uv run poe init-secrets` — Resolve 1Password secrets to `.env` and worker `.dev.vars` files (auto-runs via direnv)
- `uv run poe lint` — Run all linters (Ansible, Python, Workers, and pi extensions)
- `uv run poe lint:pi` — Lint and type-check pi extension packages
  - `--format` / `-f` — Apply Biome formatting/fixes before type-checking
- `uv run poe pi:update-deps` — Update dependencies for all tracked pi extension packages (pins pi to the currently installed version found on `PATH`)
- `uv run ruff format --check .` — Check Python formatting
- `uv run ruff check .` — Lint Python code
- `uv run basedpyright` — Type check Python code
- `ansible-lint` (in ansible/) — Lint Ansible code
- `uv run pytest` — Run unit tests (agent_harness filter plugins)

## Architecture

- `ansible/playbooks/macos.yml` — macOS playbook; `ansible/playbooks/work.yml` — Work macOS playbook; `ansible/playbooks/truenas.yml` — TrueNAS playbook; `ansible/playbooks/openclaw.yml` — OpenClaw (Debian VM) playbook; `ansible/playbooks/udmp.yml` — UDMP playbook
- `ansible/roles/` — Custom roles
- `ansible/stacks/` — Docker Compose stacks deployed to TrueNAS (`.j2` templates use centralized config)
- `ansible/config.yml` — Shared vars; `darwin.config.yml` / `work.config.yml` / `debian.config.yml` / `archlinux.config.yml` for OS/host-specific
- `ansible/models.yml` — Centralized model definitions (versions, aliases, vscode/zed config); symlinked to `chezmoi/.chezmoidata/models.yaml`
- `ansible/inventory/group_vars/truenas.yml` — TrueNAS host vars (Docker config, network IPs/ports/domains)
- `chezmoi/` — Dotfiles using chezmoi templating (`.tmpl` files use Go templates)
- `ansible/Brewfile` — Homebrew packages, casks, MAS apps
- `terraform/cloudflare/` — Cloudflare infrastructure (DNS, tunnels, Zero Trust, R2)
- `wrangler/` — Cloudflare Workers (deployed via wrangler, not Terraform)
- `cloudflare-pages/` — Static sites deployed via Cloudflare Pages (wrangler)
- `agents/` — Reusable AI agent bundles deployed via `agent_harness`
- `.agents/` / `.claude/skills/` — Project-local Claude/Pi skill sources and Claude symlinks for this repo
- `.mcp.json` / `.pi/mcp.json` — Project-scoped Cloudflare MCP configs for Claude and Pi

## OpenClaw

OpenClaw is a Debian VM running as a remote AI agent instance, reached over LAN when available and through Cloudflare Access when it is not.

- **SSH**: `ssh clawdbot` (tries `192.168.1.90:22` first, falls back to `clawdbot-ssh.thurstons.house` as `thurstonsand`)
- **Web UI**: `openclaw.thurstons.house` (behind Zero Trust)
- **Ansible**: Run `uv run poe openclaw` from openclaw itself (not remote)
- **Config**: `ansible/debian.config.yml` for apt packages and feature flags
- **Chezmoi**: Uses `{{ .chezmoi.hostname "openclaw" }}` conditionals; 1Password via `~/.local/bin/op` wrapper (chezmoi-managed)

## TrueNAS Docker Directory Layout

On TrueNAS, Docker stacks use two separate paths:

- **Compose files**: `/mnt/performance/docker/stacks/{stack}/compose.yaml`
- **Config data**: `/mnt/performance/docker/{stack}/{container}/config`

## Code Style

## Ansible

- Use FQCN for all Ansible modules (e.g., `ansible.builtin.file`, not `file`)
- YAML: 2-space indent, no trailing whitespace
- Ansible-lint enforces production profile — treat all warnings as errors

## Python

- Follow strict type hints throughout all python code

## Chezmoi

- `dot_` prefix → `.` in target; `private_` prefix → 0600 permissions (doesn't cascade to children)
- `.tmpl` suffix for Go template processing
- System info: `{{ .chezmoi.os }}`, `{{ .chezmoi.arch }}`, etc.
- Platform conditionals: `{{ if eq .chezmoi.os "darwin" }}` in templates
- Use `.chezmoiignore` for entire platform-specific files

## Adding Secrets

Secrets are stored in 1Password and cached locally via `.env` (resolved on first direnv load).

1. Add the secret reference to `.secrets.jsonc` (root of repo):

   ```jsonc
   "MY_SECRET": "op://Vault/Item/field"
   ```

2. Regenerate the cache:

   ```sh
   uv run poe init-secrets
   ```

3. Access in code:
   - **Ansible**: `{{ lookup('env', 'MY_SECRET') }}`
   - **Terraform**: Define `variable "my_secret" {}` in `variables.tf`, add `TF_VAR_my_secret` to `.secrets.jsonc`
   - **Chezmoi**: Use `op-secret` template (see below)

## Chezmoi Secrets

For secrets in dotfiles, use the `op-secret` template with a named wrapper:

1. Create a wrapper template in `.chezmoitemplates/`:

   ```gotemplate
   {{- template "op-secret" list "ENV_VAR_NAME" "op://Vault/Item/field" -}}
   ```

2. Use the wrapper in your dotfile:

   ```gotemplate
   api_key = {{ template "my-api-key" . }}
   ```

3. Add the env var to `.secrets.jsonc` and run `poe init-secrets`

This pattern allows `chezmoi apply` to use pre-resolved env vars (fast) when run via `poe local`, while still working standalone via `onepasswordRead` (slower, prompts for auth).
