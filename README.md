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

Run `mise laptop` normally. The remaining Ansible reconciliation resolves only the host credentials needed by each scoped consumer, including in check mode, and keeps Ansible's fact cache in memory so scoped values are never persisted. Native Mac-app reconciliation bypasses credential lookup in check mode. A read can require one desktop authorization; subsequent `SUDO_ASKPASS` calls reuse the scoped value without returning to 1Password.

Interactive sudo still uses TouchID as normal, including inside tmux sessions.

### Automation credentials

The shared automation identity gives fnox unattended access to the agent vault. Run `mise --no-env exec -- python3 scripts/automation_identity.py` once to enroll or rotate it through attended desktop authentication, then `mise trust` for this repository. `--no-env` allows initial enrollment before project credentials can resolve. See [the identity design](docs/designs/26-unattended-automation-identity.md) for environment boundaries.

Repo-local mise configuration loads six selected Cloudflare, Access and R2 credentials through native fnox export when entering ansiblonomicon and removes them on exit. Mise caches computed environments on disk using its native session-key encryption. Programs launched here, including Pi, inherit those six values. No secrets are exported globally. Agents launch normally without fetching the whole host set; MCPs resolve their own credentials, and Pi resolves its Parallel key only when a web operation needs it. OpenCode retains Parallel; Zed does not.

Use `scripts/fnox-host exec --secret NAME [--secret NAME ...] -- COMMAND` to give a command only its declared credentials. Selection is mandatory; there is no whole-host or `--all` mode. Agent-vault reads use the unattended identity; only consumers that actually request Private or corporate credentials use desktop authentication. Use `scripts/fnox-host get NAME` for one credential, or `mise run secrets:check NAME` to test its resolution without printing it. Do not export the automation service-account token into your shell. See [consumer-scoped credentials](docs/designs/27-consumer-scoped-credentials.md).

### Terminal theme sync

On macOS, `dark-notify` acts as the source of truth for terminal theme state. The shared [native mise capability](bootstrap/capabilities/terminal-theme/README.md) installs the runtime helpers and manages the user LaunchAgent (`dev.mise.house.thurstons.terminal-theme-watch`). Together they keep `~/.terminal-bg`, Codex, Hunk, and tmux in sync; active SSH leases mirror the personal Mac's theme to pod042. Mise renders Hunk's real-file config, while deployment and runtime switching read the same Gruvbox Hard palette assets. The watcher reloads only when its declaration or runtime inputs change.

Run `mise terminal-theme` for this capability alone, or add `--check` for a nonmutating preview. Regular laptop and pod042 reconciliation includes it and updates the standalone mise binary to latest stable when its last successful update is at least 24 hours old. Check mode skips upgrades. `mise laptop -t terminal-theme` runs natively without Ansible; mixed tags route only the remaining tags to Ansible. Neither Ansible nor chezmoi owns these theme files.

Shared Zsh startup files and static Starship/direnv configuration are also native mise resources; use `mise run shell` or `mise run shell --check`. Work rendering resolves its shell-wide Sourcegraph token and scoped sudo credential at apply time; check mode and personal/pod042 reconciliation perform no work-secret lookup. See the [shell capability](bootstrap/capabilities/shell/README.md).

The [terminal-tools capability](bootstrap/capabilities/terminal-tools/README.md) owns tmux configuration, Mac Ghostty configuration and helpers, and personal-host TPM installation. Run `mise terminal-tools` or `mise laptop -t tmux`, adding `--check` for a preview. Full reconciliation supplies software prerequisites first; focused runs assume they are installed.

### VCS client configuration

The shared [Git capability](bootstrap/capabilities/git-client/README.md) owns Git defaults, identities, signing configuration, attributes, and ignore patterns. A managed block preserves application-added settings outside it; attributes and ignore patterns are symlinked to the shared sources. The [Jujutsu capability](bootstrap/capabilities/jj-client/README.md) uses a native `conf.d` fragment, preserving the existing user config. Both independently load shared `vcs-identity` facts. SSH key provisioning remains separate.

Run `mise git-client` or `mise jj-client`, with `--check` for a preview. Regular laptop and pod042 reconciliation includes both; `mise laptop -t git-client,jj-client` runs without Ansible. Work identity and corporate URL rewrites belong in the work target's ignored `mise.local.toml`, as described in the capability README.

Temporary cutover code and its deletion conditions are tracked in the [mise migration cleanup ledger](docs/operations/mise-migration-cleanup.md). Work-host migration remains pending; keep the ledger current as capabilities move.

### Editor and Python indexes

The [Neovim capability](bootstrap/capabilities/neovim/README.md) owns editor configuration and dependency setup. Run `mise neovim` (alias `mise nvim-deps`) or add `--check` to preview configuration without upgrading dependencies. Personal hosts write Lazy's lockfile back to the shared source; work receives a copy and restores those versions. Full reconciliation runs this after software prerequisites.

Work's [Python-index capability](bootstrap/capabilities/python-index/README.md) derives uv and pip configuration from one private uv TOML value; run `mise python-index` or add `--check`. Personal hosts retain their existing absence of system index configuration. Private work SCM, Jira, and index values must be transferred as documented in [README.work.md](README.work.md) before work cutover.

### Mac runtimes and global packages

`mise mac-apps` (aliases `mise homebrew` and `mise mas`) reconciles the host's original Brewfile directly through Homebrew Bundle. The Brewfiles remain authoritative Ruby, including work extensions and `trusted`, `restart_service`, `link`, and `greedy` options. It preserves the legacy Homebrew upgrade stamp as the daily-maintenance authority, installs or upgrades only declared App Store IDs with scoped `sudo -A`, and limits cleanup to taps, formulae, and casks. `--check` parses the real Brewfile and reports drift without credentials or installs. This native capability now owns Mac application installation; the retained Ansible role is rollback/cutover cleanup state, not a playbook owner.

`mise language-tools` reconciles the inventories under `bootstrap/capabilities/language-tools/` without Ansible. It preserves unrelated global mise configuration and packages, updates only declared tools when their daily interval or inventory changes, and restores declared npm packages after Node replacement. `--check` validates the inventory and reports intended work without changing files or installing tools. Work requires its private inventory and Python-index mapping first; see [README.work.md](README.work.md).

Small vendor-installed and source-built software is also native: run `mise claude-code`, `mise opencode`, `mise pi`, `mise sessions`, `mise shp`, or `mise uvc-util`, with `--check` for a nonmutating drift report. Host registration limits each command to the laptops that declare it.

Capability-driven Node upgrades carry unmanaged registry npm globals into the new prefix at their installed versions, excluding bundled npm/Corepack. A private pending snapshot survives failed runs and is removed after successful reconciliation; linked/local packages require explicit handling before an upgrade. The self-contained Node postinstall hook restores declared packages even when Node is installed outside reconciliation.

Full laptop reconciliation ensures and maintains the standalone mise binary before Homebrew cleanup, then runs Mac apps, language tools, vendor-installed and source-built software tasks, one remaining Ansible invocation, and native configuration capabilities. `mise laptop -t homebrew,language-tools` runs only the selected native software tasks; focused language-tool runs assume their Homebrew prerequisites are already installed.

### Retiring managed paths

Add obsolete Ansible-managed paths to `.ansibleremove`. Every personal and work macOS run removes listed files, symlinks, or directories idempotently, including tagged runs. Relative and `~/` entries resolve beneath the managed user's home; absolute paths are used verbatim. Native pod042 and UDMP resources use `state = "absent"` instead.

## Structure

```text
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

- `mise laptop` — Reconcile native capabilities and the remaining macOS Ansible tasks (auto-detects work vs personal)
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
- `mise run edge:deploy` — Deploy all Workers
- `mise run edge:deploy:aig` — Deploy aig (AI Gateway proxy) Worker
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

SSH aliases are configured via chezmoi (`~/.ssh/config`). Infrastructure aliases use `ssh-smart-proxy` for LAN access with Cloudflare Access fallback. pod042 also answers on Tailscale as `pod042-ts`, and `pod042-remote` forces the Cloudflare path when the LAN probe needs bypassing.

| Target                                            | Alias        | Description             |
| ------------------------------------------------- | ------------ | ----------------------- |
| `10.10.10.42:22` / `pod042-ssh.thurstons.house`   | `ssh pod042` | Debian 13 NAS           |
| `192.168.1.89:22222` / `haos-ssh.thurstons.house` | `ssh haos`   | Home Assistant OS       |
| `192.168.1.1:22` / `udmp-ssh.thurstons.house`     | `ssh udmp`   | UniFi Dream Machine Pro |

## Platform Support

- **macOS** (Darwin) — Primary, fully supported
- **Debian** (pod042) — Physical NAS reconciled locally or over SSH with native mise bootstrap resources
- **TrueNAS** — Retired migration source; its declarations remain until replacement capabilities absorb them
- **Arch Linux** (omarchy) — Future, structure ready
