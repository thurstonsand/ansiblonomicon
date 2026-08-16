---
name: installing-software
description: Use when adding, removing, or updating software. Explains how to properly manage that installation via Ansible, which should be the default choice for all software management. Includes agent software such as skills, agents, extensions, etc.
---

# Installing Software

Use this skill when changing how software is installed in this repo.

## Start Here

- Shared package lists: `ansible/config.yml`
- Agent-harness source catalogue and host profiles: `ansible/agent-harness.config.yml`
- macOS host-specific additions: `ansible/darwin.config.yml`
- Pod042 host-specific packages and tools: `ansible/pod042.config.yml`

## macOS

- Homebrew / casks / MAS: `ansible/Brewfile`
- How Brew Bundle is applied: `ansible/playbooks/macos.yml`
- macOS-built local tools:
  - `ansible/roles/ghostty_nav/tasks/main.yml`
  - `ansible/roles/uvc_util/tasks/main.yml`

## OpenClaw / Debian

- Base apt packages: `ansible/debian.config.yml`
- External apt repos + repo packages: `ansible/debian.config.yml`
- How apt / apt repos are applied: `ansible/playbooks/openclaw.yml`

## Pod042

- Apt packages, external repositories, and host-specific language tools: `ansible/pod042.config.yml`
- Installation and role ordering: `ansible/playbooks/pod042.yml`
- Pod042 SSH identities and host configuration: `chezmoi/private_dot_ssh/`
- NFS mount and Docker environment: `ansible/playbooks/pod042.yml`, `chezmoi/dot_zshenv.tmpl`
- Run `uv run poe pod042` only on hostname `pod042`.

## Language-specific package managers

- npm globals: `ansible/config.yml`, `ansible/darwin.config.yml`, `ansible/debian.config.yml`, `ansible/pod042.config.yml`, and the corresponding host playbook
- bun globals: `ansible/config.yml`, `ansible/debian.config.yml`, `ansible/pod042.config.yml`, and the corresponding host playbook
- uv tools: `ansible/config.yml`, `ansible/pod042.config.yml`, and the corresponding host playbook
- Go tools: `ansible/config.yml`, `ansible/debian.config.yml`, `ansible/pod042.config.yml`, and the corresponding host playbook
- Rust / cargo packages: `ansible/config.yml`, `ansible/debian.config.yml`, `ansible/pod042.config.yml`, and the corresponding host playbook
- Ruby gems: `ansible/config.yml`, `ansible/darwin.config.yml`, `ansible/pod042.config.yml`, and the corresponding host playbook

## Script/install-sh based tools

- Claude Code: `ansible/playbooks/macos.yml`, `ansible/playbooks/openclaw.yml`
- opencode: `ansible/playbooks/macos.yml`, `ansible/playbooks/openclaw.yml`
- chezmoi bootstrap on Debian: `ansible/playbooks/openclaw.yml`

## Pi extensions

These are managed as dotfiles via chezmoi, then applied by Ansible through the chezmoi role.

- Pi config / extension sources: `chezmoi/private_dot_pi/agent/settings.json.tmpl`
- Local pi extension packages: `chezmoi/private_dot_pi/agent/extensions/`
- Pi custom footer/status behavior: `chezmoi/private_dot_pi/agent/extensions/pi-powerline-footer-custom/`
- How chezmoi is applied: `ansible/roles/chezmoi/tasks/main.yml`
- TypeScript agent package maintenance scripts: `scripts/pi-lint.sh`, `scripts/amp-lint.sh`, `scripts/ts-package-deps.sh`

## Skills / agents

- Source catalogue, host capability profiles, and profile exclusions: `ansible/agent-harness.config.yml`
- Host profile selection and host-only extras: `agent_harness_profile` / `agent_harness_sources_extra` in each host config
- Role defaults and supported source/plugin keys: `ansible/roles/agent_harness/defaults/main.yml`
- Target agent filesystem/layout rules: `ansible/roles/agent_harness/vars/agents.yml`
- Discovery/filter behavior: `ansible/roles/agent_harness/filter_plugins/harness_filters.py`

## Other install/update paths you may want to check

- tmux plugins: `ansible/tasks/tmux_plugins.yml`
- Periodic update scripts/timers for npm, bun, uv, cargo, gems, Go: `ansible/roles/system_maintenance/tasks/main.yml`
- Docker here is specifically for the TrueNAS instance:
  - `ansible/playbooks/truenas.yml`
  - `ansible/inventory/targets/group_vars/truenas.yml`
  - `ansible/stacks/`
  - `ansible/roles/docker_stack/tasks/main.yml`
- Ansible collections used by these playbooks: `ansible/requirements.yml`
