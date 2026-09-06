# ansiblonomicon

System configuration via Ansible + Chezmoi, replacing nix-darwin + home-manager.

## Quick Start

```bash
# First time setup (installs Xcode CLI, Homebrew, Ansible, chezmoi, 1Password CLI)
./scripts/bootstrap.sh
# Use --ignore-certs if behind a corporate proxy that intercepts TLS
./scripts/bootstrap.sh --ignore-certs

# After changes
mise laptop
```

### Sudo Access

Ansible uses `SUDO_ASKPASS` to get the sudo password from 1Password automatically. Just run `mise laptop` — no manual password entry needed.

Interactive sudo still uses TouchID as normal, including inside tmux sessions.

### Terminal theme sync

On macOS, `dark-notify` acts as the source of truth for terminal theme state. An Ansible-managed `terminal_theme` role installs a user LaunchAgent (`house.thurstons.terminal-theme-watch`), the `~/.local/bin/terminal-theme-watch` watcher, `~/.local/bin/terminal-theme-switch.py`, and the shared zsh helper at `~/.config/zsh/terminal-theme.zsh`. Together they keep `~/.terminal-bg`, Codex, Hunk, and tmux in sync while reloading the LaunchAgent only when the theme manager changes. The role owns `~/.config/hunk/config.toml` and injects the current Gruvbox Hard custom theme block from `hunk_gruvbox_theme.py`; this takes effect once the installed Hunk release supports custom themes.

### Retiring managed paths

Add obsolete Ansible-managed paths to `.ansibleremove`. Every personal and work macOS run removes listed files, symlinks, or directories idempotently, including tagged runs. Relative and `~/` entries resolve beneath the managed user's home; absolute paths are used verbatim. Native pod042 and UDMP resources use `state = "absent"` instead.

## Structure

```
├── .ansibleremove             # Retired paths removed from user-managed hosts
├── ansible/
│   ├── ansible.cfg          # Ansible configuration
│   ├── inventory/           # Host definitions
│   ├── config.yml           # Shared configuration variables
│   ├── agent-harness.config.yml # Agent skill catalogue + host capability profiles
│   ├── darwin.config.yml    # macOS-specific config
│   ├── work.config.yml     # Work macOS-specific config
│   ├── pod042.config.yml    # Retained pod042 service migration declarations
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
├── chezmoi/                  # Dotfiles managed by chezmoi
├── cloudflare-pages/         # Static sites deployed via Cloudflare Pages
├── agents/                   # Reusable AI agent bundles (source for agent_harness role)
├── .agents/                  # Project-local Claude/Pi skills for this repo
├── bootstrap/                # Native mise host bootstrap projects and remote inventory
├── terraform/cloudflare/     # Cloudflare infrastructure (DNS, tunnels, Zero Trust, R2)
├── terraform/unifi/          # UniFi Network application (VLANs, zones, WLANs, ports)
├── wrangler/                 # Cloudflare Workers (deployed via wrangler)
└── scripts/
    ├── bootstrap.sh          # One-liner bootstrap for new machines
    └── test-bootstrap.sh     # Test bootstrap in a clean macOS VM (requires tart)
```

## Commands

- `mise laptop` — Apply macOS Ansible playbook (auto-detects work vs personal)
- `mise laptop --check` — Dry-run mode (shows what would change without applying)
- `mise pod042 [capability]` — Reconcile pod042 locally or over SSH (`--check` previews changes)
- `mise udmp` — Reconcile UDM Pro host state with native mise remote bootstrap
- `mise udmp --check` — Preview UDM Pro host-state changes
- `mise run reconcile:tags [playbook]` — List the `--tags` a playbook offers (defaults to this machine's own)
- `mise run chezmoi:diff` — Preview dotfile changes (source → home), excluding lockfiles
- `mise run chezmoi:re-add` — Update source from local changes (dry-run by default, use `--apply` to apply)
- `mise run edge:init` — Terraform init (Cloudflare)
- `mise run edge:plan` — Terraform plan (Cloudflare)
- `mise run edge:apply` — Terraform apply (Cloudflare)
- `mise run edge:deploy:tesla` — Deploy Cloudflare Pages (tesla)
- `mise run edge:deploy` — Deploy all Workers (aig + hooks)
- `mise run edge:deploy:aig` — Deploy aig (AI Gateway proxy) Worker
- `mise run edge:deploy:hooks` — Deploy hooks (webhook gateway) Worker
- `mise run check` — Every non-mutating check across the repo; `mise run fix` for the mutating half
- `mise run pi:check` — Lint and type-check pi extension packages (`pi:fix` formats and autofixes first)
- `mise run amp:check` — Lint, type-check, and test Amp plugin sources
- `mise run deps:update` — Update every tracked lockfile (python + typescript)
- `mise run deps:update:ts` — Update tracked TypeScript agent packages (Pi extension packages and Amp plugin sources)
- `mise run deps:update:uv` — Upgrade `uv.lock` to the newest allowed releases and sync (personal machines only)
- `mise tasks` — List every task; `--all` includes the Go subprojects

## Design

See [nixonomicon/docs/designs/nix-to-chezmoi-ansible-migration.md](https://github.com/thurstonsand/nixonomicon/blob/main/docs/designs/nix-to-chezmoi-ansible-migration.md) for the full migration plan.

## Hosts

SSH aliases are configured via chezmoi (`~/.ssh/config`). Existing infrastructure aliases use `ssh-smart-proxy` for LAN access with Cloudflare Access fallback; pod042 is LAN-only until its Amp remote terminal is configured.

| Target                                            | Alias        | Description             |
| ------------------------------------------------- | ------------ | ----------------------- |
| `10.10.10.187:22`                                 | `ssh pod042` | Debian 13 NAS           |
| `192.168.1.89:22222` / `haos-ssh.thurstons.house` | `ssh haos`   | Home Assistant OS       |
| `192.168.1.1:22` / `udmp-ssh.thurstons.house`     | `ssh udmp`   | UniFi Dream Machine Pro |

## Platform Support

- **macOS** (Darwin) — Primary, fully supported
- **Debian** (pod042) — Physical NAS reconciled locally or over SSH with native mise bootstrap resources
- **TrueNAS** — Retired migration source; its declarations remain until replacement capabilities absorb them
- **Arch Linux** (omarchy) — Future, structure ready
