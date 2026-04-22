# ansiblonomicon

System configuration via Ansible + Chezmoi, replacing nix-darwin + home-manager.

## Quick Start

```bash
# First time setup (installs Xcode CLI, Homebrew, Ansible, chezmoi, 1Password CLI)
./scripts/bootstrap.sh
# Use --ignore-certs if behind a corporate proxy (e.g. Zscaler)
./scripts/bootstrap.sh --ignore-certs

# After changes
anup
```

### Sudo Access

Ansible uses `SUDO_ASKPASS` to get the sudo password from 1Password automatically. Just run `poe macos` or `poe work` — no manual password entry needed.

Interactive sudo still uses TouchID as normal, including inside tmux sessions.

### Terminal theme sync

On macOS, `dark-notify` now acts as the source of truth for terminal theme state. An Ansible-managed `terminal_theme` role installs a user LaunchAgent (`house.thurstons.terminal-theme-watch`), the `~/.local/bin/terminal-theme-watch` watcher, `~/.local/bin/terminal-theme-switch.py`, and the shared zsh helper at `~/.config/zsh/tmux-theme.zsh`. Together they keep `~/.terminal-bg`, Codex, and Hunk theme state in sync while reloading the LaunchAgent only when the theme manager changes. Pi uses `pi-ansi-themes` and a file-watching extension, so it follows `~/.terminal-bg` and inherits the terminal's ANSI palette instead of hardcoded colors.

## Structure

```
├── ansible/
│   ├── ansible.cfg          # Ansible configuration
│   ├── inventory/           # Host definitions (localhost, truenas)
│   ├── config.yml           # Shared configuration variables
│   ├── darwin.config.yml    # macOS-specific config
│   ├── work.config.yml     # Work macOS-specific config
│   ├── debian.config.yml    # Debian-specific config (openclaw)
│   ├── archlinux.config.yml # Arch Linux-specific config
│   ├── Brewfile             # Homebrew packages, casks, and MAS apps
│   ├── requirements.yml     # Ansible Galaxy dependencies
│   ├── roles/               # Custom and Galaxy roles
│   ├── tasks/               # Task files by category
│   ├── collections/         # Local Ansible collections (local.truenas)
│   ├── stacks/              # Docker Compose stacks for TrueNAS
│   └── playbooks/
│       ├── macos.yml        # macOS playbook
│       ├── work.yml         # Work macOS playbook
│       ├── openclaw.yml     # OpenClaw (Debian VM) playbook
│       ├── truenas.yml      # TrueNAS playbook
│       └── udmp.yml         # UDMP playbook
├── chezmoi/                  # Dotfiles managed by chezmoi
├── cloudflare-pages/         # Static sites deployed via Cloudflare Pages
├── agents/                   # Reusable AI agent bundles (source for agent_harness role)
├── .agents/                  # Project-local Claude/Pi skills for this repo
├── terraform/cloudflare/     # Cloudflare infrastructure (DNS, tunnels, Zero Trust, R2)
├── wrangler/                 # Cloudflare Workers (deployed via wrangler)
└── scripts/
    ├── bootstrap.sh          # One-liner bootstrap for new machines
    └── test-bootstrap.sh     # Test bootstrap in a clean macOS VM (requires tart)
```

## Commands

- `anup` — Apply macOS Ansible playbook (alias set up by this playbook)
- `anup --check` — Dry-run mode (shows what would change without applying)
- `poe macos` — Apply macOS Ansible playbook (same as `anup`)
- `poe work` — Apply work macOS Ansible playbook
- `poe openclaw` — Apply OpenClaw (Debian VM) Ansible playbook
- `poe truenas` — Apply TrueNAS Ansible playbook
- `poe udmp` — Apply UDMP Ansible playbook
- `poe cz-diff` — Preview dotfile changes (source → home), excluding lockfiles
- `poe cz-status` — Show files that differ between source and home
- `poe cz-re-add` — Update source from local changes (dry-run by default, use `--apply` to apply)
- `poe cz-managed` — List all files managed by chezmoi
- `poe cz-edit <file>` — Edit a managed file in source dir
- `poe tfi` — Terraform init (Cloudflare)
- `poe tfp` — Terraform plan (Cloudflare)
- `poe tfa` — Terraform apply (Cloudflare)
- `poe pages-deploy` — Deploy Cloudflare Pages (tesla)
- `poe wrangler` — Deploy all Workers (aig + hooks)
- `poe wrangler:aig` — Deploy aig (AI Gateway proxy) Worker
- `poe wrangler:hooks` — Deploy hooks (webhook gateway) Worker
- `poe lint:pi` — Lint and type-check pi extension packages (`--format` applies Biome formatting/fixes first)
- `poe pi:update-deps` — Update tracked pi extension packages to the currently installed pi version

## Design

See [nixonomicon/docs/designs/nix-to-chezmoi-ansible-migration.md](https://github.com/thurstonsand/nixonomicon/blob/main/docs/designs/nix-to-chezmoi-ansible-migration.md) for the full migration plan.

## Hosts

SSH aliases are configured via chezmoi (`~/.ssh/config`) and use `ssh-smart-proxy` to prefer LAN access with Cloudflare Access fallback:

| Target                                             | Alias          | Description                                 |
| -------------------------------------------------- | -------------- | ------------------------------------------- |
| `192.168.1.68:22` / `truenas-ssh.thurstons.house`  | `ssh truenas`  | TrueNAS SCALE server (Docker stacks, media) |
| `192.168.1.90:22` / `clawdbot-ssh.thurstons.house` | `ssh clawdbot` | OpenClaw AI agent VM                        |
| `192.168.1.89:22222` / `haos-ssh.thurstons.house`  | `ssh haos`     | Home Assistant OS                           |
| `192.168.1.1:22` / `udmp-ssh.thurstons.house`      | `ssh udmp`     | UniFi Dream Machine Pro                     |

## Platform Support

- **macOS** (Darwin) — Primary, fully supported
- **Debian** (openclaw) — OpenClaw VM, fully supported
- **Arch Linux** (omarchy) — Future, structure ready
