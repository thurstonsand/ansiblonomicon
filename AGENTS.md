# Commands

- `./scripts/bootstrap.sh` — First-time setup (installs Xcode CLI, Homebrew, Ansible, chezmoi, 1Password CLI, runs playbook)
- `./scripts/test-bootstrap.sh` — Test bootstrap in clean macOS VM via Tart
  - `--reuse` reuses existing VM; `--uninstall-xcode` tests fresh Xcode install; `--full-brew-bundle` uses real Brewfile
- `uv run poe play` — Apply Ansible playbook (uses 1Password for sudo)
- `uv run poe lint` — Lint with ansible-lint (production profile, strict)
- `uv run poe cz-diff` / `uv run poe cz-status` — Preview chezmoi changes

# Architecture

- `ansible/main.yml` — Entry playbook; `ansible/roles/` for custom roles
- `ansible/config.yml` — Shared vars; `darwin.config.yml` / `archlinux.config.yml` for OS-specific
- `chezmoi/` — Dotfiles using chezmoi templating (`.tmpl` files use Go templates)
- `ansible/Brewfile` — Homebrew packages, casks, MAS apps

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
- Secrets via 1Password: `{{ onepasswordRead "op://Vault/Item/field" }}`
