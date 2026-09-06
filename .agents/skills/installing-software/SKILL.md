---
name: installing-software
description: Use when adding, removing, or updating software, including agent skills, extensions and packages. Find its declared Ansible or native mise host configuration before changing the machine.
---

# Installing Software

Manage host software through this repo's desired state. Use the host's existing reconciliation path; inspect native resource support before adding a small adapter for a demonstrated gap.

## macOS

- Homebrew and Mac App Store apps: `ansible/Brewfile`, with `ansible/Brewfile.work` for work.
- Shared package and language-tool lists: `ansible/config.yml`; host additions in `ansible/darwin.config.yml` and `ansible/work.config.yml`.
- Reconciliation: `ansible/playbooks/macos.yml` and `ansible/playbooks/work.yml`, selected through `mise laptop`.
- Locally built utilities: the corresponding role under `ansible/roles/`, including `ghostty_nav` and `uvc_util`.
- Claude Code and opencode: their roles referenced by the macOS playbook.

## pod042

Use native mise at `bootstrap/targets/pod042/`. The remaining Ansible pod042 config and stack templates are migration references, not executable deployment authority. Never run retired Ansible playbooks on the fresh Debian host.

- Declare packages and files in the capability that owns them. `mise.repositories.toml` owns APT sources and preferences; storage's native pre-package phase installs repository files before refreshing/installing packages.
- System fnox/op tools: the `/etc/mise/host-tools.toml` declaration in `mise.base.toml`. Use normal registry backends and `latest`, with backend-managed integrity rather than handwritten version/hash installers.
- Register new capability order in `scripts/pod042_reconcile.py` and `bootstrap/mise.toml`, keeping resource ownership disjoint. Include real prerequisites in `capabilities_for`.
- Deploy through guarded `mise pod042 [capability] [--check]`, locally or from the operator machine. It verifies the exact hostname and clean, pushed, matching Git revisions.
- Read `bootstrap/targets/pod042/datasets/README.md` before changing storage layout or its migration state; full reconciliation refuses pending migrations.
- Use native `state = "absent"` for retired managed paths. A deleted source file does not remove deployed state.

## UDMP

Native capabilities live under `bootstrap/targets/udmp/`. Use `mise udmp` for OS reconciliation; Network application resources belong to OpenTofu under `terraform/unifi/`.

## Pi extensions and packages

Pi itself is installed by `ansible/roles/pi_release/`. Its extensions and package declarations are dotfiles delivered through chezmoi and the Ansible `chezmoi` role.

- Config and packages: `chezmoi/private_dot_pi/agent/settings.json.tmpl`.
- Local extension sources: `chezmoi/private_dot_pi/agent/extensions/`.
- TypeScript maintenance commands: `scripts/pi-lint.sh`, `scripts/amp-lint.sh`, `scripts/ts-package-deps.sh`.

## Skills and agents

- Source catalogue, host profiles and exclusions: `ansible/agent-harness.config.yml`.
- Host-only additions: `agent_harness_sources_extra` in the host's local config.
- Source/plugin keys: `ansible/roles/agent_harness/defaults/main.yml`.
- Harness layout: `ansible/roles/agent_harness/vars/agents.yml`.
- Resolution and filtering: `ansible/roles/agent_harness/filter_plugins/harness_filters.py`.

Keep agent configuration and skills in their declared sources rather than editing installed copies.
