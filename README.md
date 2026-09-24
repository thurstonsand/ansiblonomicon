# ansiblonomicon

System configuration through native mise capabilities and Terraform.

## Quick Start

```bash
# First time setup (Xcode CLI, Homebrew, mise, fnox, uv, 1Password CLI)
./scripts/bootstrap.sh

# After changes
mise laptop
```

### Sudo Access

Run `mise laptop` normally. Each capability resolves only the credentials it needs; laptop reconciliation has no enclosing fnox invocation. Native Mac-app reconciliation bypasses credential lookup in check mode. A read can require one desktop authorization; subsequent `SUDO_ASKPASS` calls through `scripts/sudo-askpass.sh` reuse the scoped value without returning to 1Password.

Interactive sudo still uses TouchID as normal, including inside tmux sessions.

### Automation credentials

The shared automation identity gives fnox unattended access to the agent vault. Run `mise --no-env exec -- python3 scripts/automation_identity.py` once to enroll or rotate it through attended desktop authentication, then `mise trust` for this repository. `--no-env` allows initial enrollment before project credentials can resolve. See [the identity design](docs/designs/26-unattended-automation-identity.md) for environment boundaries.

Repo-local mise configuration loads six selected Cloudflare, Access and R2 credentials through native fnox export when entering ansiblonomicon and removes them on exit. Mise caches computed environments on disk using its native session-key encryption. Programs launched here, including Pi, inherit those six values. No secrets are exported globally. Agents launch normally without fetching the whole host set; MCPs resolve their own credentials, and Pi resolves its Parallel key only when a web operation needs it. OpenCode retains Parallel; Zed does not.

Use `scripts/fnox-host exec --secret NAME [--secret NAME ...] -- COMMAND` to give a command only its declared credentials. Selection is mandatory; there is no whole-host or `--all` mode. Agent-vault reads use the unattended identity; only consumers that actually request Private or corporate credentials use desktop authentication. Use `scripts/fnox-host get NAME` for one credential, or `mise run secrets:check NAME` to test its resolution without printing it. Do not export the automation service-account token into your shell. See [consumer-scoped credentials](docs/designs/27-consumer-scoped-credentials.md).

### Terminal theme sync

On macOS, `dark-notify` acts as the source of truth for terminal theme state. The shared [native mise capability](bootstrap/capabilities/terminal-theme/README.md) installs the runtime helpers and manages the user LaunchAgent (`dev.mise.house.thurstons.terminal-theme-watch`). Together they keep `~/.terminal-bg`, Codex, Hunk, and tmux in sync; active SSH leases mirror the personal Mac's theme to pod042. Mise renders Hunk's real-file config, while deployment and runtime switching read the same Gruvbox Hard palette assets. The watcher reloads only when its declaration or runtime inputs change.

Run `mise terminal-theme` for this capability alone, or add `--check` for a nonmutating preview. Regular laptop and pod042 reconciliation includes it and updates the standalone mise binary to latest stable when its last successful update is at least 24 hours old. Check mode skips upgrades. `mise laptop -t terminal-theme` runs only this capability. Both laptops reject unsupported tags before taking action.

Shared Zsh startup files and static Starship configuration are also native mise resources; use `mise run shell` or `mise run shell --check`. Work rendering resolves its shell-wide Sourcegraph token and scoped sudo credential at apply time; check mode and personal/pod042 reconciliation perform no work-secret lookup. This repo's environment uses mise; direnv remains installed with its automatic shell hook for external projects. See the [shell capability](bootstrap/capabilities/shell/README.md).

The [terminal-tools capability](bootstrap/capabilities/terminal-tools/README.md) owns tmux configuration, Mac Ghostty configuration and helpers, and personal-host TPM installation. Run `mise terminal-tools` or `mise laptop -t tmux`, adding `--check` for a preview. Full reconciliation supplies software prerequisites first; focused runs assume they are installed.

The [user-tools capability](bootstrap/capabilities/user-tools/README.md) owns shared LazyGit, SourceKit-LSP, Vim and markdownlint configuration plus standalone helpers. Personal hosts also receive GitHub CLI and Rustup settings. Run `mise user-tools` or `mise laptop -t user-tools`, adding `--check` for a nonmutating preview.

The [desktop-tools capability](bootstrap/capabilities/desktop-tools/README.md) links application configuration to first-party repository sources. Go's local telemetry mode is shared by both Macs; four additional configurations are personal-only. Run `mise desktop-tools` or `mise laptop -t desktop-tools`; no credentials are required.

### VCS client configuration

The shared [Git capability](bootstrap/capabilities/git-client/README.md) owns Git defaults, identities, signing configuration, attributes, and ignore patterns. A managed block preserves application-added settings outside it; attributes and ignore patterns are symlinked to the shared sources. The [Jujutsu capability](bootstrap/capabilities/jj-client/README.md) uses a native `conf.d` fragment, preserving the existing user config. Both independently load shared `vcs-identity` facts. SSH key provisioning remains separate.

Run `mise git-client` or `mise jj-client`, with `--check` for a preview. Regular laptop and pod042 reconciliation includes both; `mise laptop -t git-client,jj-client` runs only those two. Work identity and corporate URL rewrites belong in the work target's ignored `mise.local.toml`, as described in the capability README.

### Editor and Python indexes

The [editor-config capability](bootstrap/capabilities/editor-config/README.md) is the source of truth for Zed on both Macs and for the personal Mac's VSCode-family and Datasette LLM configuration. `bootstrap/capabilities/agent-harness/models.yml` is the shared model catalogue. Run `mise editor-config` or add `--check`; previews use explicit non-secret placeholders and never resolve credentials.

The [Neovim capability](bootstrap/capabilities/neovim/README.md) owns editor configuration and dependency setup. Run `mise neovim` (alias `mise nvim-deps`) or add `--check` to preview configuration without upgrading dependencies. Personal hosts write Lazy's lockfile back to the shared source; work receives its separate `lazy-lock.work.json` and restores those versions. Full reconciliation runs this after software prerequisites.

Work's [Python-index capability](bootstrap/capabilities/python-index/README.md) derives uv and pip configuration from one private uv TOML value; run `mise python-index` or add `--check`. Personal hosts have no system index configuration. Private work SCM, Jira, and index values live in ignored work target files documented in [README.work.md](README.work.md).

### Mac runtimes and global packages

`mise mac-apps` (aliases `mise homebrew` and `mise mas`) reconciles the host's Brewfile under `bootstrap/capabilities/mac-apps/` directly through Homebrew Bundle. The Brewfiles remain authoritative Ruby, including private `Brewfile.work.*` extensions beside `Brewfile.work`, and `trusted`, `restart_service`, `link`, and `greedy` options. It keeps a Homebrew upgrade stamp as the daily-maintenance authority, installs or upgrades only declared App Store IDs with scoped `sudo -A`, limits cleanup to taps, formulae, and casks, and then upgrades all eligible installed formulae (including transitive dependencies, but not pinned formulae or casks) when daily maintenance is due. `--check` parses the real Brewfile and reports both Bundle and eligible formula drift without credentials, installs, or stamp writes.

`mise language-tools` reconciles the inventories under `bootstrap/capabilities/language-tools/`. It preserves unrelated global mise configuration and packages, updates only declared tools when their daily interval or inventory changes, and restores declared npm packages after Node replacement. `--check` validates the inventory and reports intended work without changing files or installing tools. Work requires its private inventory and Python-index mapping first; see [README.work.md](README.work.md).

Small vendor-installed and source-built software is also native: run `mise claude-code`, `mise opencode`, `mise pi`, `mise sessions`, `mise shp`, or `mise uvc-util`, with `--check` for a nonmutating drift report. Host registration limits each command to the laptops that declare it. Go and UVC sources live under `bootstrap/capabilities/software/sources/`.

Capability-driven Node upgrades carry unmanaged registry npm globals into the new prefix at their installed versions, excluding bundled npm/Corepack. A private pending snapshot survives failed runs and is removed after successful reconciliation; linked/local packages require explicit handling before an upgrade. The self-contained Node postinstall hook restores declared packages even when Node is installed outside reconciliation.

Full laptop reconciliation ensures and maintains the standalone mise binary before Homebrew cleanup, then runs Mac apps, language tools, vendor-installed and source-built software, system configuration, agent deployment, and user configuration. Work also applies its private `work-local` files after the Python index. `mise laptop -t homebrew,language-tools` runs only the selected native software tasks; focused language-tool runs assume their Homebrew prerequisites are already installed.

The [macOS system capability](bootstrap/capabilities/macos-system/README.md) owns typed preferences, sudo Touch ID, and personal hostname. Run `mise sysconfig` or `mise laptop -t dock,finder`, adding `--check` for a preview. Apps restart only when their preferences change; work hostname and existing work `pam_reattach` lines remain unmanaged.

### Agent catalogue

On both Macs, `mise agent-harness` reconciles skills, subagents, and hook fragments through the [native catalogue capability](bootstrap/capabilities/agent-harness/README.md). `--check` compares cached sources without refreshing them; `--cached` applies those same cached sources. Normal apply refreshes declared Git sources at most once per day. Exact-file ownership preserves independently installed skills, Claude's `synced/` tree, and existing parent-directory permissions.

`bootstrap/capabilities/agent-harness/configuration/` is the canonical source for harness settings, instructions, extensions, plugins, and shared libraries. `mise agent-config --check` previews with non-secret placeholders and exits 2 when secret-backed parity remains unresolved; add `--real-secrets` for read-only parity with scoped fnox resolution, or omit `--check` to apply. Static first-party assets are symlinked; rendered, host-dependent, and private outputs are regular files, with private outputs mode `0600`. Host-local non-secret inputs belong in `bootstrap/capabilities/agent-harness/local/<hostname>/data.toml`; credentials remain SecretRefs resolved only for the command.

`mise agent-harness` reconciles the catalogue and then calls `agent-config`. Full reconciliation routes both through the `agent-harness` tag. A host's private plugin sources belong in the ignored `bootstrap/capabilities/agent-harness/local/<hostname>/catalogue.toml`. Hosted Amp publication uses the same catalogue, resolver, and `publish_amp_skills.py`.

### Retiring managed paths

Deleting a source alone does not remove deployed state. Declare a `state = "absent"` resource in the capability that owns the path, and delete the declaration once every affected host has converged.

## Structure

```text
├── cloudflare-pages/         # Static sites deployed via Cloudflare Pages
├── agents/                   # Locally authored plugins selected by the native agent catalogue
├── .agents/                  # Project-local Claude/Pi skills for this repo
├── bootstrap/                # Native mise capabilities, agent catalogue, host targets, and remote inventory
├── terraform/cloudflare/     # Cloudflare infrastructure (DNS, tunnels, Zero Trust, R2)
├── terraform/unifi/          # UniFi Network application (VLANs, zones, WLANs, ports)
├── wrangler/                 # Cloudflare Workers (deployed via wrangler)
└── scripts/
    ├── bootstrap.sh          # One-liner bootstrap for new machines
    └── test-bootstrap.sh     # Test bootstrap in a clean macOS VM (requires tart)
```

## Commands

- `mise laptop` — Reconcile native capabilities (auto-detects work vs personal)
- `mise laptop --check` — Dry-run mode (shows what would change without applying)
- `mise pod042 [capability]` — Reconcile pod042 locally or over SSH (`--check` previews changes)
- `mise udmp` — Reconcile UDM Pro host state with native mise remote bootstrap
- `mise udmp --check` — Preview UDM Pro host-state changes
- `mise run reconcile:tags` — List this host's native tags
- `mise run edge:init` — Terraform init (Cloudflare)
- `mise run edge:plan` — Terraform plan (Cloudflare)
- `mise run edge:apply` — Terraform apply (Cloudflare)
- `mise run edge:deploy:tesla` — Deploy Cloudflare Pages (tesla)
- `mise run edge:deploy` — Deploy aig and hooks Workers
- `mise run edge:deploy:aig` — Deploy aig (AI Gateway proxy) Worker
- `mise run edge:deploy:doppelclaude` — Deploy the dedicated [Doppelclaude proxy](docs/doppelclaude.md)
- `mise run check` — Every non-mutating check across the repo; `mise run fix` for the mutating half
- `mise run pi:check` — Lint and type-check pi extension packages (`pi:fix` formats and autofixes first)
- `mise run amp:check` — Lint, type-check, and test Amp plugin sources
- `mise run deps:update` — Update every tracked lockfile (python + typescript)
- `mise run deps:update:ts` — Update tracked TypeScript agent packages (Pi extension packages and Amp plugin sources)
- `mise run deps:update:uv` — Upgrade `uv.lock` to the newest allowed releases and sync (personal machines only)
- `mise tasks` — List every task; `--all` includes the Go subprojects

## Design

The earlier Nix-to-Ansible/chezmoi migration is documented in [nixonomicon/docs/designs/nix-to-chezmoi-ansible-migration.md](https://github.com/thurstonsand/nixonomicon/blob/main/docs/designs/nix-to-chezmoi-ansible-migration.md).

## Hosts

SSH aliases are configured by the [SSH client capability](bootstrap/capabilities/ssh-client/README.md), which owns `~/.ssh/config` and `ssh-smart-proxy` without pruning unrelated SSH state. Infrastructure aliases use the proxy for LAN access with Cloudflare Access fallback. pod042 also answers on Tailscale as `pod042-ts`, and `pod042-remote` forces the Cloudflare path when the LAN probe needs bypassing. pod042 alone receives its GitHub key pair through two scoped secrets. Run `mise ssh-client` or `mise laptop -t ssh-client`; checks use non-secret placeholders.

| Target                                            | Alias        | Description             |
| ------------------------------------------------- | ------------ | ----------------------- |
| `10.10.10.42:22` / `pod042-ssh.thurstons.house`   | `ssh pod042` | Debian 13 NAS           |
| `192.168.1.89:22222` / `haos-ssh.thurstons.house` | `ssh haos`   | Home Assistant OS       |
| `192.168.1.1:22` / `udmp-ssh.thurstons.house`     | `ssh udmp`   | UniFi Dream Machine Pro |

## Platform Support

- **macOS** (Darwin) — Primary, fully supported
- **Debian** (pod042) — Physical NAS reconciled locally or over SSH with native mise bootstrap resources
- **TrueNAS** — Retired; historical migration notes only
- **Arch Linux** (omarchy) — Future; no active target
