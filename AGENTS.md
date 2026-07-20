# Skills

When working with TrueNAS (SSH, Docker containers, stacks, debugging services), **always load the `truenas-docker-ops` skill first**. It contains essential paths, commands, and helper scripts.

## Commands

- `./scripts/bootstrap.sh` — First-time setup on a brand new machine (installs Xcode CLI, Homebrew, Ansible, chezmoi, 1Password CLI)
  - `--ignore-certs` — Skip SSL verification for `ansible-galaxy install` (for corporate proxies)
- `./scripts/test-bootstrap.sh` — Test bootstrap in clean macOS VM via Tart
  - `--reuse` reuses existing VM; `--uninstall-xcode` tests fresh Xcode install; `--full-brew-bundle` uses real Brewfile
- `uv run poe laptop` — Apply macOS Ansible playbook (auto-detects work vs personal by hostname)
  - `--check` / `-c` — Dry-run mode (no changes made)
  - `--tags` / `-t` — Only run tasks with specific tags (comma-separated)
  - **macOS tags**: `agent-harness`, `chezmoi`/`dotfiles`, `claude-code`, `ghosttykit`, `homebrew`/`mas`, `language-tools`, `neovim`/`nvim-deps`, `opencode`, `sessions`, `shp`, `sysconfig`/`hostname`, `terminal-theme`, `tmux`, `uvc-util`
  - **macOS defaults tags**: `desktop-services`, `dock`, `finder`, `menubar`, `nsglobaldomain`, `permissions`
  - **Work-only tags**: `agent-harness`, `chezmoi`/`dotfiles`, `ghosttykit`, `git-hooks`, `homebrew`, `language-tools`, `local`, `neovim`/`nvim-deps`, `pi`, `sessions`, `terminal-theme`, `uvc-util`
- `uv run poe truenas` — Apply TrueNAS Ansible playbook (same options as macos)
  - **TrueNAS tags**: `docker`/`docker-networks`, `docker-stack-role` (all Docker stacks), `truenas-apps`, `vm`/`truenas-vm`, `openclaw-vm`, `homeassistant-vm`, or individual stacks: `anypod`, `arr-apps`, `caddy`, `cli-proxy-api`, `cloudflared`, `ddclient`, `ghost`, `homepage`, `isponsorblocktv`, `scrypted`, `torrent`, `watchtower`
- `uv run poe udmp` — Apply UDMP Ansible playbook (same options as macos)
  - **UDMP tags**: `multicast-querier`, `nextdns`
- `uv run poe openclaw` — Apply OpenClaw Ansible playbook (playbook selects local on hostname `openclaw`, otherwise remote over SSH; override with `--target openclaw_local|openclaw_remote`)
  - `--check` / `-c` — Dry-run mode (no changes made)
  - `--tags` / `-t` — Only run tasks with specific tags (comma-separated)
  - **OpenClaw tags**: `apt`, `apt-repos`, `uv`, `mise`, `secrets`/`onepassword`/`op`, `chezmoi`/`dotfiles`, `claude-code`, `ghosttykit`, `opencode`, `system-maintenance`/`timers`, `language-tools`, `sshd`/`ssh`, `shpool`, `pi-extensions`, `sessions`, `tmux`, `motd`, `agent-harness`
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
- `uv run poe lint` — Run all linters (Ansible, Python, Workers, Pi extensions, session-recovery, Amp plugins, and CLI tools)
- `uv run poe lint:pi` — Lint and type-check pi extension packages
  - `--format` / `-f` — Apply Biome formatting/fixes before type-checking
- `uv run poe lint:session-recovery` — Lint and type-check the shared `@thurstons/session-recovery` library and its agent consumers
  - `--format` / `-f` — Apply Biome formatting/fixes before type-checking
- `uv run poe lint:amp` — Format, lint, and type-check Amp plugins
- `uv run poe ts:update-deps` — Update dependencies for tracked TypeScript agent packages (pins Pi packages to the installed `pi` version and updates Amp plugin deps)
- `uv run ruff format --check .` — Check Python formatting
- `uv run ruff check .` — Lint Python code
- `uv run basedpyright` — Type check Python code
- `ansible-lint` (in ansible/) — Lint Ansible code
- `uv run pytest` — Run unit tests (agent_harness filter plugins)

## Architecture

- `ansible/playbooks/macos.yml` — macOS playbook; `ansible/playbooks/work.yml` — Work macOS playbook; `ansible/playbooks/truenas.yml` — TrueNAS playbook; `ansible/playbooks/openclaw.yml` — OpenClaw (Debian VM) playbook; `ansible/playbooks/udmp.yml` — UDMP playbook
- `ansible/roles/` — Custom roles
- `ansible/stacks/` — Docker Compose stacks deployed to TrueNAS (`.j2` templates use centralized config)
- `truenas_apps` in `ansible/inventory/targets/group_vars/truenas.yml` — TrueNAS catalog apps managed through the in-repo `local.truenas.app` module
- `ansible/config.yml` — Shared vars; `darwin.config.yml` / `work.config.yml` / `openclaw.config.yml` / `debian.config.yml` / `archlinux.config.yml` for OS/host-specific
- `ansible/models.yml` — Centralized model definitions (versions, aliases, vscode/zed config); symlinked to `chezmoi/.chezmoidata/models.yaml`
- `ansible/session-title-prompt.txt` — Session title prompt shared by chezmoi and agent_harness skills; symlinked to `chezmoi/.chezmoitemplates/session-title-prompt`
- `.ansibleremove` — Retired files/directories removed on every personal macOS, work macOS, and OpenClaw run
- `ansible/inventory/group_vars/truenas.yml` — TrueNAS host vars (Docker config, network IPs/ports/domains)
- `chezmoi/` — Dotfiles using chezmoi templating (`.tmpl` files use Go templates)
- `chezmoi/dot_config/amp/plugins/` — Amp plugin sources managed as a local TypeScript package; check with `uv run poe lint:amp`
- `ansible/Brewfile` — Homebrew packages, casks, MAS apps
- `terraform/cloudflare/` — Cloudflare infrastructure (DNS, tunnels, Zero Trust, R2)
- `wrangler/` — Cloudflare Workers (deployed via wrangler, not Terraform)
- `cloudflare-pages/` — Static sites deployed via Cloudflare Pages (wrangler)
- `agents/` — Reusable AI agent bundles deployed via `agent_harness`; skills may use `SKILL.md.j2` for Jinja2 templating at deploy time
- `.agents/` / `.claude/skills/` — Project-local Claude/Pi skill sources and Claude symlinks for this repo
- `.mcp.json` / `.pi/mcp.json` — Project-scoped Cloudflare MCP configs for Claude and Pi

## OpenClaw

OpenClaw is being rebuilt fresh as a TrueNAS-hosted Debian VM. The old Debian VM (`clawdbot`) and the temporary Docker stack are legacy reference state only.

- **Web UI**: `openclaw.thurstons.house` (behind Zero Trust)
- **VM target IP**: `192.168.1.90` (`clawdbot` is permanently retired; this address is reused)
- **TrueNAS VM modeling**: use `local.truenas.vm` from the in-repo collection; manage stable VM core fields and selected devices only
- **Guest playbook**: `uv run poe openclaw` or direct `ansible-playbook -i ansible/inventory/targets/openclaw.yml ansible/playbooks/openclaw.yml`; target auto-selects local on hostname `openclaw`, otherwise remote
- **Secrets direction**: scoped 1Password `agent` vault via service-account token and `op` SecretRefs; do not restore legacy plaintext gateway env drop-ins

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
