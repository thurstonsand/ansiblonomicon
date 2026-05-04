---
name: installing-software
description: Use when adding, removing, or updating software. Explains how to properly manage that installation via Ansible, which should be the default choice for all software management. Includes agent software such as skills, agents, extensions, etc.
---

# Installing Software

Use this skill when changing how software is installed in this repo.

## Start Here

- Shared package lists and agent-harness sources: `ansible/config.yml`
- macOS host-specific additions: `ansible/darwin.config.yml`
- OpenClaw/Debian host-specific additions: `ansible/debian.config.yml`

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

## Language-specific package managers

- npm globals: `ansible/config.yml`, `ansible/darwin.config.yml`, `ansible/debian.config.yml`, `ansible/playbooks/macos.yml`, `ansible/playbooks/openclaw.yml`
- bun globals: `ansible/config.yml`, `ansible/debian.config.yml`, `ansible/playbooks/macos.yml`, `ansible/playbooks/openclaw.yml`
- uv tools: `ansible/config.yml`, `ansible/playbooks/macos.yml`, `ansible/playbooks/openclaw.yml`
- Go tools: `ansible/config.yml`, `ansible/debian.config.yml`, `ansible/playbooks/macos.yml`, `ansible/playbooks/openclaw.yml`
- Rust / cargo packages: `ansible/config.yml`, `ansible/debian.config.yml`, `ansible/playbooks/openclaw.yml`
- Ruby gems: `ansible/config.yml`, `ansible/darwin.config.yml`, `ansible/playbooks/macos.yml`, `ansible/playbooks/openclaw.yml`

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
- Pi extension maintenance scripts: `scripts/pi-lint.sh`, `scripts/pi-extension-deps.sh`

## Skills / agents

- Source and target configuration: `ansible/config.yml`
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
