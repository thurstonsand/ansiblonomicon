# ansiblonomicon

System configuration via Ansible + Chezmoi, replacing nix-darwin + home-manager.

## Quick Start

```bash
# First time setup (installs Xcode CLI, Homebrew, Ansible, chezmoi, 1Password CLI)
./scripts/bootstrap.sh
# Use --ignore-certs if behind a corporate proxy that intercepts TLS
./scripts/bootstrap.sh --ignore-certs

# After changes
uv run poe laptop
```

### Sudo Access

Ansible uses `SUDO_ASKPASS` to get the sudo password from 1Password automatically. Just run `poe laptop` — no manual password entry needed.

Interactive sudo still uses TouchID as normal, including inside tmux sessions.

### Terminal theme sync

On macOS, `dark-notify` acts as the source of truth for terminal theme state. An Ansible-managed `terminal_theme` role installs a user LaunchAgent (`house.thurstons.terminal-theme-watch`), the `~/.local/bin/terminal-theme-watch` watcher, `~/.local/bin/terminal-theme-switch.py`, and the shared zsh helper at `~/.config/zsh/terminal-theme.zsh`. Together they keep `~/.terminal-bg`, Codex, Hunk, and tmux in sync while reloading the LaunchAgent only when the theme manager changes. The role owns `~/.config/hunk/config.toml` and injects the current Gruvbox Hard custom theme block from `hunk_gruvbox_theme.py`; this takes effect once the installed Hunk release supports custom themes.

### Retiring managed paths

Add obsolete Ansible-managed paths to `.ansibleremove`. Every personal macOS, work macOS, pod042, and OpenClaw run removes listed files, symlinks, or directories idempotently, including tagged runs. Relative and `~/` entries resolve beneath the managed user's home; absolute paths are used verbatim. TrueNAS and UDMP do not consume this manifest.

## Structure

```
├── .ansibleremove             # Retired paths removed from user-managed hosts
├── ansible/
│   ├── ansible.cfg          # Ansible configuration
│   ├── inventory/           # Host definitions (localhost, truenas, openclaw)
│   ├── config.yml           # Shared configuration variables
│   ├── darwin.config.yml    # macOS-specific config
│   ├── work.config.yml     # Work macOS-specific config
│   ├── openclaw.config.yml  # Retained OpenClaw reference config
│   ├── pod042.config.yml    # pod042 Debian dev VM config
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
│       ├── openclaw.yml     # Retained OpenClaw reference playbook
│       ├── pod042.yml       # pod042 local-only playbook
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

- `poe laptop` — Apply macOS Ansible playbook (auto-detects work vs personal)
- `poe laptop --check` — Dry-run mode (shows what would change without applying)
- `poe openclaw` — Apply the retained OpenClaw reference playbook
- `poe pod042` — Converge pod042 from inside its persistent checkout
- `poe truenas` — Apply TrueNAS Ansible playbook
- `poe udmp` — Apply UDMP Ansible playbook
- `poe list-tags [playbook]` — List the `--tags` a playbook offers (defaults to this machine's own)
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
- `poe lint:amp` — Format, lint, and type-check Amp plugin sources
- `poe ts:update-deps` — Update tracked TypeScript agent packages (Pi extension packages and Amp plugin sources)

## Design

See [nixonomicon/docs/designs/nix-to-chezmoi-ansible-migration.md](https://github.com/thurstonsand/nixonomicon/blob/main/docs/designs/nix-to-chezmoi-ansible-migration.md) for the full migration plan.

## Hosts

SSH aliases are configured via chezmoi (`~/.ssh/config`). Existing infrastructure aliases use `ssh-smart-proxy` for LAN access with Cloudflare Access fallback; pod042 is LAN-only until its Amp remote terminal is configured.

| Target                                            | Alias         | Description                                 |
| ------------------------------------------------- | ------------- | ------------------------------------------- |
| `192.168.1.68:22` / `truenas-ssh.thurstons.house` | `ssh truenas` | TrueNAS SCALE server (Docker stacks, media) |
| `192.168.1.94:22`                                 | `ssh pod042`  | Debian development VM                       |
| `192.168.1.89:22222` / `haos-ssh.thurstons.house` | `ssh haos`    | Home Assistant OS                           |
| `192.168.1.1:22` / `udmp-ssh.thurstons.house`     | `ssh udmp`    | UniFi Dream Machine Pro                     |

## Platform Support

- **macOS** (Darwin) — Primary, fully supported
- **Debian** (pod042) — Local-only, self-converging development VM
- **TrueNAS** — Docker stacks plus first-class VM modeling via the in-repo `local.truenas` collection
- **Arch Linux** (omarchy) — Future, structure ready
