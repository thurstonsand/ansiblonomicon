# ansiblonomicon

System configuration via Ansible + Chezmoi, replacing nix-darwin + home-manager.

## Quick Start

```bash
# First time setup (installs Xcode CLI, Homebrew, Ansible, chezmoi, 1Password CLI, runs playbook)
./scripts/bootstrap.sh

# After changes
anup
```

### Sudo Access

Ansible uses `op run` with `SUDO_ASKPASS` to get the sudo password from 1Password automatically.
Just run `poe local` — no manual password entry needed.

Interactive sudo still uses TouchID as normal.

## Structure

```
├── ansible/
│   ├── ansible.cfg          # Ansible configuration
│   ├── inventory/           # Host definitions (localhost, truenas)
│   ├── config.yml           # Shared configuration variables
│   ├── darwin.config.yml    # macOS-specific config
│   ├── archlinux.config.yml # Arch Linux-specific config
│   ├── Brewfile             # Homebrew packages, casks, and MAS apps
│   ├── requirements.yml     # Ansible Galaxy dependencies
│   ├── roles/               # Custom and Galaxy roles
│   ├── tasks/               # Task files by category
│   ├── collections/         # Local Ansible collections (local.truenas)
│   ├── stacks/              # Docker Compose stacks for TrueNAS
│   └── playbooks/
│       ├── local.yml        # Local machine playbook
│       └── truenas.yml      # TrueNAS playbook
├── chezmoi/                  # Dotfiles managed by chezmoi
├── cloudflare-pages/         # Static sites deployed via Cloudflare Pages
├── terraform/cloudflare/     # Cloudflare infrastructure (DNS, tunnels, Zero Trust, R2, Workers)
└── scripts/
    ├── bootstrap.sh          # One-liner bootstrap for new machines
    └── test-bootstrap.sh     # Test bootstrap in a clean macOS VM (requires tart)
```

## Commands

- `anup` — Apply local Ansible playbook (alias set up by this playbook)
- `anup --check` — Dry-run mode (shows what would change without applying)
- `poe truenas` — Apply TrueNAS Ansible playbook
- `poe cz-diff` — Preview dotfile changes (source → home)
- `poe cz-status` — Show files that differ between source and home
- `poe cz-re-add` — Update source from local changes (dry-run by default, use `--apply` to apply)
- `poe cz-managed` — List all files managed by chezmoi
- `poe cz-edit <file>` — Edit a managed file in source dir
- `poe tfi` — Terraform init (Cloudflare)
- `poe tfp` — Terraform plan (Cloudflare)
- `poe tfa` — Terraform apply (Cloudflare)
- `poe pages-deploy` — Deploy Cloudflare Pages (tesla)
- `poe worker-secret` — Set API_KEY secret for llms Worker (run after tfa)

## Design

See [nixonomicon/docs/designs/nix-to-chezmoi-ansible-migration.md](https://github.com/thurstonsand/nixonomicon/blob/main/docs/designs/nix-to-chezmoi-ansible-migration.md) for the full migration plan.

## Platform Support

- **macOS** (Darwin) — Primary, fully supported
- **Arch Linux** (omarchy) — Future, structure ready
