# ansiblonomicon

System configuration via Ansible + Chezmoi, replacing nix-darwin + home-manager.

## Quick Start

```bash
# First time setup (installs Homebrew, Ansible, runs playbook)
./scripts/bootstrap.sh

# After changes
anup
```

### Sudo Access

Ansible uses `become_password_file` to get the sudo password from 1Password automatically.
Just run `poe play` — no manual password entry needed.

Interactive sudo still uses TouchID as normal.

## Structure

```
├── ansible/
│   ├── ansible.cfg          # Ansible configuration
│   ├── inventory            # Host definitions (localhost)
│   ├── config.yml           # Shared configuration variables
│   ├── darwin.config.yml    # macOS-specific config
│   ├── archlinux.config.yml # Arch Linux-specific config
│   ├── Brewfile             # Homebrew packages, casks, and MAS apps
│   ├── requirements.yml     # Ansible Galaxy dependencies
│   ├── roles/               # Custom and Galaxy roles
│   ├── tasks/               # Task files by category
│   └── main.yml             # Entry point playbook
├── chezmoi/                  # Dotfiles (coming soon)
└── scripts/
    └── bootstrap.sh          # One-liner bootstrap for new machines
```

## Commands

- `anup` — Apply Ansible configuration (alias set up by this playbook)
- `chezmoi apply` — Apply dotfile changes
- `chezmoi diff` — Preview dotfile changes

## Design

See [nixonomicon/docs/designs/nix-to-chezmoi-ansible-migration.md](https://github.com/thurstonsand/nixonomicon/blob/main/docs/designs/nix-to-chezmoi-ansible-migration.md) for the full migration plan.

## Platform Support

- **macOS** (Darwin) — Primary, fully supported
- **Arch Linux** (omarchy) — Future, structure ready
