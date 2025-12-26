# Commands

- `./scripts/bootstrap.sh` — First-time setup (installs Xcode CLI, Homebrew, Ansible, chezmoi, 1Password CLI, runs playbook)
- `./scripts/test-bootstrap.sh` — Test bootstrap in clean macOS VM via Tart
  - `--reuse` reuses existing VM; `--uninstall-xcode` tests fresh Xcode install; `--full-brew-bundle` uses real Brewfile
- `uv run poe local` — Apply local Ansible playbook (uses 1Password for sudo)
  - `--check` / `-c` — Dry-run mode (no changes made)
  - `--tags` / `-t` — Only run tasks with specific tags (comma-separated)
- `uv run poe truenas` — Apply TrueNAS Ansible playbook (same options as local)
- `uv run poe lint` — Lint with ansible-lint (production profile, strict)
- `uv run poe cz-diff` / `uv run poe cz-status` — Preview chezmoi changes
- `uv run poe tfi` / `uv run poe tfp` / `uv run poe tfa` — Terraform init/plan/apply (Cloudflare infrastructure)
- `uv run poe pages-deploy` — Deploy Cloudflare Pages (tesla)

# Architecture

- `ansible/playbooks/local.yml` — Local machine playbook; `ansible/playbooks/truenas.yml` — TrueNAS playbook
- `ansible/roles/` — Custom roles
- `ansible/config.yml` — Shared vars; `darwin.config.yml` / `archlinux.config.yml` for OS-specific
- `chezmoi/` — Dotfiles using chezmoi templating (`.tmpl` files use Go templates)
- `ansible/Brewfile` — Homebrew packages, casks, MAS apps
- `terraform/cloudflare/` — Cloudflare infrastructure (DNS, tunnels, Zero Trust, R2)
- `cloudflare-pages/` — Static sites deployed via Cloudflare Pages (wrangler)

# Code Style

- Use FQCN for all Ansible modules (e.g., `ansible.builtin.file`, not `file`)
- YAML: 2-space indent, no trailing whitespace
- Ansible-lint enforces production profile — treat all warnings as errors

# Chezmoi Patterns

- `dot_` prefix → `.` in target; `private_` prefix → 0600 permissions (doesn't cascade to children)
- `.tmpl` suffix for Go template processing
- System info: `{{ .chezmoi.os }}`, `{{ .chezmoi.arch }}`, etc.
- Platform conditionals: `{{ if eq .chezmoi.os "darwin" }}` in templates
- Use `.chezmoiignore` for entire platform-specific files

# Adding Secrets

Secrets are stored in 1Password and accessed via the `op` CLI.

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

3. Add the env var to `ansible/.env.op`:
   ```sh
   ENV_VAR_NAME=op://Vault/Item/field
   ```

This pattern allows `chezmoi apply` to use pre-resolved env vars (fast) when run via `poe local`, while still working standalone via `onepasswordRead` (slower, prompts for auth).

## Ansible Secrets

Add secret references to `ansible/.env.op` — they're resolved once by `op run` at playbook start:

```sh
MY_SECRET=op://Vault/Item/field
```

Access in playbooks via `{{ lookup('env', 'MY_SECRET') }}`.

## Terraform Secrets

Add secret references to `terraform/cloudflare/.env.op` — they're resolved by `op run` when running `poe tfi/tfp/tfa`:

```sh
TF_VAR_my_secret=op://Vault/Item/field
```

Access in Terraform via `var.my_secret` (define the variable in `variables.tf`).
