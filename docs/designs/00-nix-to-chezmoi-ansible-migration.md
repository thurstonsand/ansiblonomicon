# Migration from Nix to Chezmoi + Ansible

## Problem Statement

The current Nix-based configuration (nix-darwin + home-manager) has become too inflexible and painful to maintain. The goal is to migrate to a more approachable stack:

- **Chezmoi**: Dotfile management with templating
- **Ansible**: System configuration, package management, macOS defaults
- **direnv**: Local development environments (replacing nix develop)

Requirements:

1. **Gradual migration**: Decomission nix pieces as chezmoi+ansible equivalents come online
2. **Multi-platform ready**: Structure should support macOS (current) and future omarchy (Arch Linux)
3. **Single entry point**: Ansible drives everything, including chezmoi
4. **Zero nix at the end**: Complete elimination of nix-darwin/home-manager
5. **Fail fast**: Start with the most complex Ansible work to surface issues early

## Current Nix Configuration Inventory

### System-Level Configuration (nix-darwin)

| Component                    | File                                  | Complexity | Migration Target                        |
| ---------------------------- | ------------------------------------- | ---------- | --------------------------------------- |
| Homebrew taps/brews/casks    | `darwin/system/homebrew.nix`          | HIGH       | Ansible (geerlingguy.mac.homebrew role) |
| Mac App Store apps           | `darwin/system/homebrew.nix`          | MEDIUM     | Ansible (geerlingguy.mac.mas role)      |
| macOS system defaults        | `darwin/system/macos.nix`             | HIGH       | Ansible (custom osx task)               |
| Nix system packages          | `darwin/system/packages.nix`          | LOW        | Ansible homebrew + direct installs      |
| launchd agents               | `darwin/system/launchd.nix`           | MEDIUM     | Ansible launchd module                  |
| User configuration           | `darwin/system/users.nix`             | LOW        | Ansible vars                            |
| Fonts                        | `darwin/system/default.nix`           | LOW        | Ansible homebrew cask fonts             |
| PAM TouchID                  | `darwin/system/default.nix`           | LOW        | Ansible pam module                      |
| Enhanced homebrew validation | `darwin/system/enhanced-homebrew.nix` | LOW        | Custom Ansible task                     |

### Home-Manager Configuration (User-Level)

| Component                                       | File              | Complexity | Migration Target                   |
| ----------------------------------------------- | ----------------- | ---------- | ---------------------------------- |
| Git config + signing                            | `common/home.nix` | MEDIUM     | Chezmoi template                   |
| SSH config                                      | `common/home.nix` | MEDIUM     | Chezmoi template                   |
| Zsh config (profileExtra, initContent, aliases) | `common/home.nix` | HIGH       | Chezmoi templates                  |
| Starship prompt                                 | `common/home.nix` | LOW        | Chezmoi                            |
| Program enables (bat, btop, eza, fzf, etc.)     | `common/home.nix` | LOW        | Ansible packages + Chezmoi configs |
| Jujutsu config                                  | `common/home.nix` | LOW        | Chezmoi                            |
| Vim config + plugins                            | `common/home.nix` | LOW        | Chezmoi                            |
| NVChad                                          | `common/home.nix` | MEDIUM     | Chezmoi + manual plugin install    |
| direnv config                                   | `common/home.nix` | LOW        | Chezmoi                            |
| Nix-index + comma                               | `common/home.nix` | N/A        | DROP (nix-specific)                |
| Home packages                                   | `common/home.nix` | LOW        | Ansible homebrew                   |
| Darwin-specific packages                        | `darwin/home.nix` | LOW        | Ansible homebrew                   |
| Default app associations (duti)                 | `darwin/home.nix` | MEDIUM     | Ansible task                       |
| Session PATH/variables                          | `darwin/home.nix` | LOW        | Chezmoi .zprofile                  |

### Dotfiles (Direct File Management)

| Dotfile             | Source                                             | Platform                | Migration        |
| ------------------- | -------------------------------------------------- | ----------------------- | ---------------- |
| ghostty config      | `darwin/dotfiles/.config/ghostty/`                 | macOS                   | Chezmoi          |
| nextdns.conf        | `darwin/dotfiles/.config/nextdns.conf`             | macOS                   | Chezmoi          |
| rclone config       | `common/dotfiles/.config/rclone/`                  | shared                  | Chezmoi          |
| lazygit config      | `common/dotfiles/.config/lazygit/`                 | shared                  | Chezmoi          |
| .vimrc              | `common/dotfiles/.vimrc`                           | shared                  | Chezmoi          |
| Storj uplink config | `common/platform_dependent_dotfiles/storj-uplink/` | platform-specific paths | Chezmoi template |

### Scripts

| Script                                     | Purpose              | Migration              |
| ------------------------------------------ | -------------------- | ---------------------- |
| `darwin/system/scripts/brew-autoupdate.sh` | Auto-update homebrew | Ansible task + launchd |

### Unmanaged Configs to Capture

These are in your home directory but not currently managed by Nix:

| Config          | Location                                         | Notes                                                         |
| --------------- | ------------------------------------------------ | ------------------------------------------------------------- |
| opencode        | `~/.config/opencode/`                            | AGENTS.md, config.json, opencode.jsonc                        |
| amp             | `~/.config/amp/`                                 | AGENTS.md, settings.json, skills, commands                    |
| zed             | `~/.config/zed/`                                 | settings.json, keymap.json, themes                            |
| linearmouse     | `~/.config/linearmouse/`                         | Mouse customization                                           |
| raycast         | `~/.config/raycast/`                             | Raycast settings                                              |
| BetterTouchTool | `~/Library/Application Support/BetterTouchTool/` | Gestures/shortcuts                                            |
| other apps      | various                                          | for each installed app, see if there's config worth capturing |

## Design Decisions

### 1. Repository Structure

```
~/Develop/ansiblonomicon/
├── ansible/
│   ├── inventory/
│   │   └── hosts.yml             # localhost + future remote hosts
│   ├── group_vars/
│   │   ├── all.yml               # shared variables
│   │   ├── darwin.yml            # macOS-specific vars
│   │   └── archlinux.yml         # future omarchy vars
│   ├── roles/
│   │   ├── homebrew/             # custom or use geerlingguy.mac.homebrew
│   │   ├── macos-defaults/       # system.defaults equivalent
│   │   ├── launchd/              # launchd agents
│   │   ├── packages/             # cross-platform package installation
│   │   └── chezmoi/              # apply chezmoi from ansible
│   ├── playbooks/
│   │   ├── darwin.yml            # full macOS setup
│   │   ├── archlinux.yml         # future omarchy
│   │   └── common.yml            # shared tasks
│   ├── files/
│   │   └── scripts/              # standalone scripts (brew-autoupdate.sh)
│   ├── requirements.yml          # ansible-galaxy dependencies
│   ├── ansible.cfg
│   └── main.yml                  # entry point playbook
├── chezmoi/
│   ├── .chezmoi.toml.tmpl        # chezmoi config template
│   ├── .chezmoiignore
│   ├── .chezmoiexternal.toml     # external sources (e.g., oh-my-zsh)
│   ├── dot_config/
│   │   ├── git/
│   │   │   └── config.tmpl       # git config with templating
│   │   ├── ghostty/
│   │   │   └── config            # macOS only
│   │   ├── lazygit/
│   │   │   └── config.yml
│   │   ├── starship.toml
│   │   ├── amp/
│   │   │   └── AGENTS.md
│   │   ├── opencode/
│   │   │   ├── AGENTS.md
│   │   │   └── opencode.jsonc
│   │   └── zed/
│   │       └── settings.json
│   ├── dot_ssh/
│   │   └── config.tmpl           # SSH config with platform conditionals
│   ├── dot_zshrc.tmpl
│   ├── dot_zprofile.tmpl
│   ├── dot_vimrc
│   └── private_dot_config/       # for sensitive configs
│       └── rclone/
│           └── rclone.conf
├── scripts/
│   └── bootstrap.sh              # one-liner bootstrap
└── README.md
```

### 2. Single Entry Point: Ansible

The main entry point is `ansible/main.yml`:

```yaml
---
- name: Bootstrap system
  hosts: localhost
  connection: local

  vars_files:
    - group_vars/all.yml
    - "group_vars/{{ ansible_os_family | lower }}.yml"

  pre_tasks:
    - name: Install chezmoi
      # Platform-specific installation

  roles:
    - role: packages # Install all packages (homebrew/pacman/etc)
    - role: macos-defaults # macOS system preferences (when darwin)
    - role: launchd # launchd agents (when darwin)
    - role: chezmoi # Apply dotfiles last

  tasks:
    - name: Apply chezmoi
      command: chezmoi apply --force
      changed_when: true
```

### 3. Platform Detection Strategy

Chezmoi templates use:

```
{{ if eq .chezmoi.os "darwin" }}
# macOS specific
{{ else if eq .chezmoi.os "linux" }}
# Linux (omarchy) specific
{{ end }}
```

Ansible uses:

```yaml
when: ansible_os_family == "Darwin"
```

### 4. Integration with geerlingguy/mac-dev-playbook

**Worth incorporating:**

- `geerlingguy.mac.homebrew` role - battle-tested homebrew management
- `geerlingguy.mac.mas` role - Mac App Store app installation
- `geerlingguy.mac.dock` role - dock configuration
- `elliotweiser.osx-command-line-tools` role - ensures xcode CLI tools
- Task structure: `tasks/osx.yml` for system defaults
- Config structure: `default.config.yml` pattern for defaults + `config.yml` for overrides

**Skip:**

- `geerlingguy.dotfiles` role - we're using chezmoi instead
- Sublime Text configuration - not using

### 5. Secrets Management

Options:

- **1Password CLI** (recommended for your setup since you already use 1Password)
- chezmoi's built-in 1Password integration: `{{ onepasswordRead "op://vault/item/field" }}`
- git-crypt for repo secrets (you already use this)

## Edge Cases & Failure Modes

| Scenario                 | Handling                                            |
| ------------------------ | --------------------------------------------------- |
| Homebrew not installed   | Bootstrap script installs it first                  |
| MAS apps require sign-in | Ansible skips with warning, user signs in manually  |
| 1Password not signed in  | Chezmoi templates fail gracefully with placeholders |
| Partial run failure      | Ansible idempotency allows re-running safely        |
| Platform mismatch        | ansible_os_family and chezmoi.os guards             |
| First run vs update      | chezmoi diff shows changes before apply             |

## Rejected Alternatives

### Using Nix alongside Chezmoi

- Rejected because: The goal is zero nix. Nix complexity was the original pain point.

### Using GNU Stow instead of Chezmoi

- Rejected because: No templating, no cross-platform support, no secrets management.

### Ansible-only (no Chezmoi)

- Rejected because: Ansible's file management is verbose for dotfiles. Chezmoi's templating and diff preview are superior for this use case.

### Chezmoi-only (no Ansible)

- Rejected because: Chezmoi can't manage homebrew, system defaults, launchd agents, or packages effectively. Ansible excels at these.

## Implementation Plan

Ordered by complexity (highest first) to fail fast:

### Phase 1: Foundation + Homebrew (HIGHEST COMPLEXITY)

- [x] Create new repo at `~/Develop/ansiblonomicon`
- [x] Set up Ansible with `geerlingguy.mac.homebrew` role
- [x] Migrate all taps, brews, casks from `homebrew.nix`
- [x] Set up 1Password integration for become password (single biometric prompt)
- [x] Test: Full homebrew management works independently
- [x] Migrate Mac App Store apps (using geerlingguy.mac.mas role)

### Phase 2: macOS System Defaults (HIGH COMPLEXITY)

- [x] Create `roles/macos-defaults/` with all settings from `macos.nix`
- [x] Migrate dock settings
- [x] Migrate finder settings
- [x] Migrate NSGlobalDomain settings
- [x] Migrate menu bar clock settings
- [x] Add PAM sudo configuration (password before TouchID for automation)
- [x] Add PAM TouchID for sudo (if not already enabled)
- [x] Test: `defaults read` shows expected values

### Phase 3: Chezmoi Bootstrap (MEDIUM COMPLEXITY)

- [x] Initialize chezmoi repo structure
- [x] Create `.chezmoi.toml.tmpl` with platform detection
- [x] Migrate simple dotfiles first:
  - [x] `.vimrc`
  - [x] lazygit config
  - [x] ghostty config
  - [x] nextdns.conf
- [x] Test: `chezmoi diff` shows no changes after apply

### Phase 4: Shell Configuration (MEDIUM COMPLEXITY)

- [x] Create `.zshrc.tmpl` with:
  - [x] evalcache function
  - [x] fzf/zoxide/starship/direnv integration
  - [x] Completion optimization
  - [x] History settings
  - [x] Key bindings
  - [x] Aliases (shared + platform-specific)
- [x] Create `.zprofile.tmpl` with:
  - [x] PATH setup (homebrew, npm-global, opencode, rustup)
  - [x] Platform-specific profile (brew shellenv, orbstack)
- [x] Migrate starship config
- [x] Test: New shell starts correctly with all features

### Phase 5: Git + SSH Configuration (MEDIUM COMPLEXITY)

- [x] Create git config template with:
  - [x] User info
  - [x] Signing configuration (1Password integration)
  - [x] Aliases
  - [x] Core settings
  - [x] Platform-specific paths
- [x] Create SSH config template with:
  - [x] 1Password agent socket (macOS)
  - [x] Host configurations
  - [x] Platform conditionals
- [x] Test: `git commit -S` works, SSH to hosts works

### Phase 6: Program Configurations (LOW COMPLEXITY)

- [x] rclone config (with secrets via 1Password or git-crypt)
- [x] Storj uplink config (platform-specific paths)
- [x] jujutsu config
- [x] direnv config

### Phase 7: Package Installation (LOW COMPLEXITY)

- [x] Add all CLI tools to ansible/Brewfile:
  - [x] ack, ast-grep, bat, btop, bun, cmake, deno, direnv, duti, eza
  - [x] fh, fzf, gh, git, git-credential-manager, git-crypt, git-delta, git-trim
  - [x] go, htop, imagemagick, jq, jujutsu, just, lazygit
  - [x] nextdns, node, opentofu, prettyping, rclone, restic, ripgrep
  - [x] sqlite-utils, starship, storj-uplink, tldr, tree, unzip, uv, vim, zoxide
- [x] Handle nix-only packages (DROPPED):
  - nvchad → manual installation if needed
  - nix-prefetch-github, nix-inspect, nixd, nil, cf-terraforming → not needed without Nix

### Phase 8: Default Applications (LOW COMPLEXITY)

- [x] Create chezmoi `run_onchange` script for duti file associations
  - Uses `codeEditor` variable from `.chezmoi.toml.tmpl` as single source of truth
  - Maps editor command to bundle ID automatically
  - Re-runs when `codeEditor` changes
- [x] Create `~/.local/bin/code` symlink pointing to configured editor
- [x] Editor reference table in `.chezmoi.toml.tmpl` with all supported editors

### Phase 9: Delta Wrapper (LOW COMPLEXITY)

- [x] Create delta wrapper script in chezmoi for auto light/dark mode
- [x] Added git-delta to Brewfile
- [x] Ensure `~/.local/bin` is first in PATH (after brew shellenv)

### Phase 10: Capture Unmanaged Configs (LOW COMPLEXITY)

- [x] Add opencode config to chezmoi
- [x] Add amp config to chezmoi
- [x] Add zed config to chezmoi
- [x] Add linearmouse config to chezmoi
- [x] Evaluate BetterTouchTool export
- [x] Document any configs that can't be version controlled

### Phase 11: Bootstrap Script (LOW COMPLEXITY)

- [x] Create `scripts/bootstrap.sh` that:
  - [x] Installs Xcode CLI tools (non-interactive via softwareupdate)
  - [x] Installs Homebrew
  - [x] Installs Ansible via Homebrew
  - [x] Installs chezmoi via Homebrew
  - [x] Installs ansible-galaxy requirements
  - [x] Runs the main playbook
- [x] Create `scripts/test-bootstrap.sh` for VM testing with Tart
- [x] Create `ansible/Brewfile.test` for minimal test runs
- [x] Test on clean macOS VM (via Tart)

### Phase 12: Decommission Nix (FINAL) ✅

- [x] Verify all functionality works via chezmoi+ansible
- [x] Comprehensive sweep for unmigrated darwin/mac configs
- [x] Added missing items from sweep:
  - [x] Fonts (font-fontawesome, font-mononoki-nerd-font) to Brewfile
  - [x] Hostname configuration via ansible.builtin.hostname
  - [x] XDG_CONFIG_HOME export in zshenv
  - [x] Go telemetry config (~/Library/Application Support/go/telemetry/mode)
- [x] Remove nix symlinks from home directory
- [x] Uninstall nix-darwin (`sudo nix run nix-darwin#darwin-uninstaller`)
- [x] Uninstall Determinate Nix (`/nix/nix-installer uninstall`)
- [x] Clear evalcache (`rm -rf ~/.cache/zsh/*`)
- [x] Clean up shell config: switch `__CHEZMOI_ZSHENV_ENV_CONFIGURED` back to `__ZSHENV_ENV_CONFIGURED` in .zshenv
- [x] Archive nixonomicon repo (or repurpose for NAS-only)

### Phase 13: Migrate Terraform State to Cloud Storage ✅

Storing tfstate in git (even encrypted) is bad practice — no locking, no collaboration safety, secrets in history.

- [x] Move terraform/ from nixonomicon to ansiblonomicon
- [x] Create Cloudflare R2 bucket for tfstate storage
- [x] Configure R2 in S3-compatible mode as Terraform backend
- [x] Migrate secrets from git-crypt to 1Password (`op run` with `.env.op`)
- [x] Migrate existing tfstate to R2 (`tofu init -migrate-state`)
- [x] Add `*.tfstate` and `*.tfstate.backup` to .gitignore
- [x] Add Dependabot config for provider updates
- [x] Add poe tasks: `tfi`, `tfp`, `tfa`
- [x] Delete terraform/ from nixonomicon

### Phase 14: Cloudflare Pages Migration

Currently Cloudflare Pages are managed via files + CI. Migrate to Terraform for consistency.

- [x] Audit current cloudflare-pages/ directory structure
- [x] Create Terraform resources for pages projects
- [x] Migrate deployment configuration to Terraform
- [x] Remove cloudflare-pages/ directory and CI workflow
- [x] Test deployments work via Terraform

### Phase 15: Migrate Encrypted Secrets to 1Password

Many secrets are currently in git-crypt encrypted files. Migrate to chezmoi's 1Password integration.

- [x] Audit .gitattributes for all encrypted files
- [x] For each encrypted file, create 1Password item
- [x] Update chezmoi templates to use `{{ onepasswordRead "op://..." }}`
- [ ] Remove secrets from git-crypt
- [ ] Update .gitattributes

### Phase 16: Shell Alias Setup ✅

Replace the nix `switch` alias with `anup` for Ansible.

- [x] Add `anup` alias to zsh config (via chezmoi)
- [x] Alias runs: `(cd ~/Develop/ansiblonomicon && poe play)`
- [x] Add `anup --check` for dry-run mode
- [x] Document in README

### Phase 17: TrueNAS Management via Ansible

Full "NAS as Code" management of TrueNAS SCALE via Ansible over SSH, using a custom `local.truenas` collection for middleware API access plus a `docker_stack` role for container lifecycle.

**Platform notes:**

- TrueNAS SCALE "Electric Eel" (24.10) today, upgrading to "Fangtooth" (25.04) soon
- Apps are Docker-backed on 24.10+; custom apps use Docker Compose YAML
- Middleware/midclt-driven automation is more stable long-term than REST (deprecated in 25.04+)
- OS-level package installs not supported; may enable Developer Mode for minimal CLI tools (git-crypt, jq, ripgrep) and re-apply post-upgrade

**Design evolution:** Original plan called for `arensb.truenas` collection, but we built a custom `local.truenas` collection instead. This gives us tighter control, simpler action plugins, and avoids bugs/limitations in the external dependencies (e.g. deprecated apis).

**Ansible Collection:** `local.truenas` (in-repo at `ansible/collections/ansible_collections/local/truenas/`)

Thin wrappers around TrueNAS SCALE's `midclt` CLI, executed via SSH. Action plugins run on controller with full Python 3.12+ features; only raw `midclt call` commands execute on TrueNAS. Modules implemented:

| Category  | Modules              | Notes                        |
| --------- | -------------------- | ---------------------------- |
| Storage   | `pool_scrub`         | Pool scrub tasks             |
| Storage   | `pool_snapshottask`  | Periodic snapshot scheduling |
| Shares    | `sharing_smb`        | SMB shares                   |
| Shares    | `sharing_nfs`        | NFS shares                   |
| Services  | `service`            | Service enable/start/stop    |
| Services  | `smart_test`         | SMART test schedules         |
| Lifecycle | `initshutdownscript` | Init/shutdown scripts        |

**Scope:**

1. **Core TrueNAS configuration ("NAS as code"):**

   - Shares: SMB shares/service, NFS shares/service ✅
   - Ops: periodic snapshot tasks, scrub tasks, SMART tests ✅
   - Services: cifs, nfs, ssh, ups, smartd ✅
   - Init scripts: WOL enable ✅
   - _Not yet implemented:_ datasets (compression, quotas, recordsize), users, groups, hostname, system dataset, certificates

2. **Container/app lifecycle:**

   - Deploy Docker Compose stacks from Git-controlled definitions ✅
   - Render .env files from 1Password secrets (via Jinja2 templates) ✅
   - Lifecycle via SSH (docker compose up -d) ✅
   - Network creation (external macvlan Docker networks) ✅

3. **Shell environment:**
   - _Not yet implemented:_ Dotfiles stored on persistent dataset, symlinked via initscript

**Out of scope (managed via TrueNAS UI):**

- ZFS pool creation/destruction (too risky for automation)
- Network/VLAN configuration (rarely changes, hardware-dependent)
- OS updates (remain through TrueNAS UI)

**Current implementation:**

_TrueNAS Apps (2, managed by TrueNAS UI — leave as-is):_

- storj-node, plex

_Docker Compose Stacks deployed (12 in ansible/stacks/):_

- arr-apps (sonarr, radarr, prowlarr, overseerr, flaresolverr, huntarr, recyclarr)
- torrent (gluetun + qbittorrent)
- frigate, scrypted
- cloudflared, ddclient
- homepage, ghost
- anypod, isponsorblocktv
- arcane, cli-proxy-api

_Stacks not migrated:_

- homeassistant (runs as TrueNAS VM, not Docker)
- sshd, privatebin, obsidian-livesync, podsync, unifi-client-check, orb, grafana, watchtower (deprecated and no longer using)
- mosquitto, zwave-js-ui (migrated to homeassistant VM, removed from TrueNAS)

_Shares configured:_

| Type | Name                  | Path                                         | Notes           |
| ---- | --------------------- | -------------------------------------------- | --------------- |
| SMB  | windows               | /mnt/capacity/backup/windows                 | ✅              |
| SMB  | thurston-personal-mbp | /mnt/capacity/backup/timemachine/thurston-\* | Time Machine ✅ |
| SMB  | watch                 | /mnt/capacity/watch                          | ✅              |
| NFS  | docker                | /mnt/performance/docker                      | ✅              |
| NFS  | watch                 | /mnt/capacity/watch                          | ✅              |

_Scheduled Tasks configured:_

| Type     | Target      | Schedule          | Retention  |
| -------- | ----------- | ----------------- | ---------- |
| Snapshot | performance | every 6h          | 3 days ✅  |
| Snapshot | performance | monthly           | 1 month ✅ |
| Scrub    | performance | weekly Tue 4am    | ✅         |
| Scrub    | capacity    | weekly Tue 4am    | ✅         |
| SMART    | all disks   | short daily 00:00 | ✅         |
| SMART    | all disks   | long 1st of mo    | ✅         |

_Services enabled:_ cifs, nfs, ssh, ups, smartd ✅

_Docker Networks (macvlan):_ trusted, iot, external, personal ✅

_Init Scripts:_ WOL enable ✅

**Repository structure (actual):**

```
ansible/
├── collections/ansible_collections/local/truenas/  # Custom TrueNAS collection
│   └── plugins/
│       ├── action/           # Action plugins (run on controller)
│       ├── modules/          # Module definitions
│       └── plugin_utils/     # midclt helper
├── inventory/
│   ├── truenas.yml           # TrueNAS host definition
│   └── group_vars/
│       └── truenas.yml       # Docker config, network IPs/ports/domains
├── playbooks/
│   └── truenas.yml           # TrueNAS playbook (flat tasks, no roles)
├── roles/
│   └── docker_stack/         # Generic Docker Compose deployment role
└── stacks/                   # Docker Compose files (.j2 templates)
    ├── arr-apps/
    ├── cloudflared/
    └── ...
```

**Implementation status:**

- [x] Create `ansible/inventory/truenas.yml` with TrueNAS host
- [x] Create `ansible/inventory/group_vars/truenas.yml` with Docker config, network IPs/ports/domains
- [x] Create `ansible/playbooks/truenas.yml` entry playbook
- [x] Build custom `local.truenas` collection with action plugins for:
  - [x] `service` - service enable/start/stop
  - [x] `smart_test` - SMART test schedules
  - [x] `pool_scrub` - pool scrub tasks
  - [x] `pool_snapshottask` - snapshot scheduling
  - [x] `sharing_smb` - SMB shares
  - [x] `sharing_nfs` - NFS shares
  - [x] `initshutdownscript` - init/shutdown scripts
- [x] Migrate stacks from nixonomicon/nas/stacks/ to ansible/stacks/
- [x] Create `docker_stack` role for Docker Compose deployment:
  - [x] Sync compose files to TrueNAS (Jinja2 templates)
  - [x] Render .env files from 1Password secrets
  - [x] Run `docker compose up -d` for each stack
- [x] Create Docker network tasks for macvlan networks
- [x] Create `poe truenas` task for TrueNAS-specific playbook
- [ ] Add `local.truenas` modules for datasets, users, groups (if needed)
- [ ] dotfile symlinks
- [ ] Test: Full playbook run is idempotent
- [ ] Delete nas/stacks/ from nixonomicon after migration complete

### Phase 18: VM Configuration Capture

TrueNAS VMs (HomeAssistant, Z-Wave JS UI) are currently configured manually via the TrueNAS UI. Capture VM definitions in Ansible for reproducibility.

**Scope:**

- VM definitions (CPU, memory, disk, network)
- Boot order and device passthrough (USB Z-Wave stick)
- Cloud-init or first-boot configuration where applicable

**Out of scope:**

- VM internal configuration (managed by the VM's own config management)
- Live migration or snapshot automation

**Investigation needed:**

- [ ] Determine if TrueNAS middleware exposes VM CRUD via midclt
- [ ] Audit current VM configs via UI or `midclt call vm.query`
- [ ] Evaluate complexity vs benefit (VMs rarely change)

**Implementation:**

- [ ] Add `vm` module to `local.truenas` collection (if middleware supports it)
- [ ] Create VM definitions in `truenas.yml` playbook or group_vars
- [ ] Test: VM can be recreated from Ansible definition

## Testing Strategy

1. **Incremental testing**: After each phase, verify the specific functionality
2. **Diff verification**: `chezmoi diff` should show no unexpected changes
3. **Idempotency**: Running `ansible-playbook main.yml` twice should report no changes
4. **Clean install test**: Final validation on fresh macOS (VM or new user account)

## Rollback Strategy

During migration:

- Keep nix-darwin fully functional until Phase 12
- Each phase can be reverted by running `darwin-rebuild switch`
- Chezmoi supports `chezmoi forget` to stop managing files
- Git history preserves all changes

## Success Criteria

1. ✅ Single command (`./scripts/bootstrap.sh` or `ansible-playbook main.yml`) configures entire system
2. ✅ All dotfiles managed by chezmoi with proper templating
3. ✅ All packages installed via Ansible (homebrew/native package manager)
4. ✅ All macOS defaults configured via Ansible
5. ✅ Zero nix dependencies remaining
6. ✅ Structure ready for omarchy (Arch Linux) addition
7. ✅ Local dev environments work via direnv (without nix)
