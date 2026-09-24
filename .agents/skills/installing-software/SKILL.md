---
name: installing-software
description: Use when adding, removing, or updating software, including agent skills, extensions and packages. Find its native mise declaration before changing the machine.
---

# Installing Software

Manage host software through this repo's desired state. Use the host's existing reconciliation path; inspect native resource support before adding a small adapter for a demonstrated gap.

## macOS

- Homebrew and Mac App Store apps: `bootstrap/capabilities/mac-apps/Brewfile`, with `Brewfile.work` for work; reconcile through `mise mac-apps`. Work's private additions go in an ignored `Brewfile.work.*` beside it.
- Runtime and global-package inventories: `bootstrap/capabilities/language-tools/`; work's private inventory lives in its native target. Reconcile through `mise language-tools`.
- Reconciliation: `mise laptop` runs every registered native capability. Work's private files belong to the `work-local` capability.
- Claude Code, OpenCode, sessions, shp, and uvc-util: `bootstrap/capabilities/software/`, registered under the Mac targets. Go and UVC overlay sources live in its `sources/` directory. Use the matching root task with `--check` before applying; UVC reconciliation builds but never runs camera settings.

## pod042

Use native mise at `bootstrap/targets/pod042/`; its target resources are the deployment authority.

- Do not install packages directly except for temporary diagnosis. Declare packages and files in the capability that owns them. `mise.repositories.toml` owns APT sources, signing keys, and preferences; native pre-package hooks install repository files before refreshing or installing packages.
- Containerized applications belong in a Compose project under `bootstrap/targets/pod042/containers/stacks/` and a matching native `[bootstrap.compose]` declaration. Let Compose own service dependencies, health, networks, and image references rather than installing an equivalent host package.
- System fnox/op tools: the `/etc/mise/host-tools.toml` declaration in `mise.base.toml`. Use normal registry backends and `latest`, with backend-managed integrity rather than handwritten version/hash installers.
- Register new capability order in `scripts/pod042_reconcile.py` and `bootstrap/mise.toml`, keeping resource ownership disjoint. Include real prerequisites in `capabilities_for`.
- Deploy through `mise pod042 [capability] [--check]`. Remote operation verifies the exact hostname and clean, pushed, matching Git revisions; host-local operation uses the current checkout so an intentional working change can be tested before commit.
- Read `bootstrap/targets/pod042/datasets/README.md` before changing storage layout or its migration state; full reconciliation refuses pending migrations.
- Use native `state = "absent"` for retired managed paths. After it converges away everywhere relevant, remove the temporary declaration and source. A source deletion alone does not remove deployed state.

## UDMP

Native capabilities live under `bootstrap/targets/udmp/`. Use `mise udmp` for OS reconciliation; Network application resources belong to OpenTofu under `terraform/unifi/`.

## Pi extensions and packages

Work's Pi release is declared in `bootstrap/targets/ML-DFC6YK6VJQ/mise.pi.toml` and reconciled through `mise pi`; personal Pi belongs to the language-tool npm inventory. Native agent configuration owns Pi settings, extensions, and package declarations.

- Config renderer and package declarations: `bootstrap/capabilities/agent-harness/configuration/pi.py` and `assets.toml`.
- Local extension sources: `bootstrap/capabilities/agent-harness/configuration/assets/pi/extensions/`.
- Reconcile configuration with `mise agent-config --check`, then `mise agent-config` to apply.
- TypeScript maintenance commands: `scripts/pi-lint.sh`, `scripts/amp-lint.sh`, `scripts/ts-package-deps.sh`.

## Skills and agents

- Source catalogue, host profiles and exclusions: `bootstrap/capabilities/agent-harness/{catalogue,profiles}.toml`.
- Harness layout: `bootstrap/capabilities/agent-harness/harnesses/`.
- Source/plugin keys, resolution and filtering: `bootstrap/capabilities/agent-harness/harness_filters.py`.
- Host-private catalogue additions: an ignored `bootstrap/capabilities/agent-harness/local/<hostname>/catalogue.toml` holding a `[[sources]]` array.
- Hosted Amp publication: native `bootstrap/capabilities/agent-harness/publish_amp_skills.py`, invoked by `scripts/publish-amp-skills.sh`.

Keep agent configuration and skills in their declared sources rather than editing installed copies.
