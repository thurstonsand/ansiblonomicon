# Skills

When working with TrueNAS (SSH, Docker containers, stacks, debugging services), **always load the `truenas-docker-ops` skill first**. It contains essential paths, commands, and helper scripts.

# Commands

- `./scripts/bootstrap.sh` — First-time setup on a brand new machine (installs Xcode CLI, Homebrew, Ansible, chezmoi, 1Password CLI)
- `./scripts/test-bootstrap.sh` — Test bootstrap in clean macOS VM via Tart
  - `--reuse` reuses existing VM; `--uninstall-xcode` tests fresh Xcode install; `--full-brew-bundle` uses real Brewfile
- `uv run poe local` — Apply local Ansible playbook
  - `--check` / `-c` — Dry-run mode (no changes made)
  - `--tags` / `-t` — Only run tasks with specific tags (comma-separated)
- `uv run poe truenas` — Apply TrueNAS Ansible playbook (same options as local)
- `uv run poe cz-diff` / `uv run poe cz-status` — Preview chezmoi changes
- `uv run poe tfi` / `uv run poe tfp` / `uv run poe tfa` — Terraform init/plan/apply (Cloudflare infrastructure)
  - `--yes` / `-y` — Auto-approve apply (no confirmation prompt)
- `uv run poe pages-deploy` — Deploy Cloudflare Pages (tesla)
- `uv run poe wrangler` — Deploy all Workers (llms + aig)
- `uv run poe wrangler:llms` — Deploy llms Worker via Wrangler (includes secrets, observability)
  - `--force-secret` / `-f` — Update API_KEY secret even if it exists
- `uv run poe wrangler:aig` — Deploy aig (AI Gateway proxy) Worker via Wrangler
  - `--force-secret` / `-f` — Update secrets even if they exist

# Dev Commands

- `uv run poe init-secrets` — Resolve 1Password secrets to `.env.secrets` (auto-runs via direnv)
- `uv run poe lint` — Run all linters (combines all below)
- `uv run ruff format --check .` — Check Python formatting
- `uv run ruff check .` — Lint Python code
- `uv run basedpyright` — Type check Python code
- `ansible-lint` (in ansible/) — Lint Ansible code
- `uv run pytest` — Run unit tests (agent_harness filter plugins)

# Architecture

- `ansible/playbooks/local.yml` — Local machine playbook; `ansible/playbooks/truenas.yml` — TrueNAS playbook
- `ansible/roles/` — Custom roles
- `ansible/stacks/` — Docker Compose stacks deployed to TrueNAS (`.j2` templates use centralized config)
- `ansible/config.yml` — Shared vars; `darwin.config.yml` / `archlinux.config.yml` for OS-specific
- `ansible/inventory/group_vars/truenas.yml` — TrueNAS host vars (Docker config, network IPs/ports/domains)
- `chezmoi/` — Dotfiles using chezmoi templating (`.tmpl` files use Go templates)
- `ansible/Brewfile` — Homebrew packages, casks, MAS apps
- `terraform/cloudflare/` — Cloudflare infrastructure (DNS, tunnels, Zero Trust, R2)
- `wrangler/` — Cloudflare Workers (deployed via wrangler, not Terraform)
- `cloudflare-pages/` — Static sites deployed via Cloudflare Pages (wrangler)
- `agents/` — Local AI agent skills deployed via `agent_harness` role

## TrueNAS Docker Directory Layout

On TrueNAS, Docker stacks use two separate paths:

- **Compose files**: `/mnt/performance/docker/stacks/{stack}/compose.yaml`
- **Config data**: `/mnt/performance/docker/{stack}/{container}/config`

# Cloudflare Worker Logs

**Real-time tail** (requires terminal that stays open):

```sh
cd terraform/cloudflare && wrangler tail llms --format pretty
```

**Historical logs via CLI** (requires cached secrets):

```sh
./scripts/worker-logs.sh             # Query last 60 minutes
./scripts/worker-logs.sh -m 30       # Query last 30 minutes
./scripts/worker-logs.sh --list-queries  # List saved queries
```

**Historical logs via Dashboard**: Cloudflare Dashboard → Workers & Pages → select worker → Logs tab

# Code Style

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

# Adding Secrets

Secrets are stored in 1Password and cached locally via `.env.secrets` (resolved on first direnv load).

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
