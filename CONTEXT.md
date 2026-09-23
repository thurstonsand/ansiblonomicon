# Context

- **Ansiblonomicon**: This repo. The single declarative source for every machine I own — laptops, NAS, router, dev VM, and for the Cloudflare edge in front of them.
- **Host**: A machine this repo configures through a native mise bootstrap target under `bootstrap/targets/`. Work also retains an Ansible playbook and inventory for unmigrated private consumers.
- **Reconcile**: One host run bringing the machine to its declared state. The unit of applying change; always re-runnable, always safe to repeat.
- **Tag**: A selector for partial laptop reconciliation. Personal tags select native capabilities; work also accepts its remaining Ansible tags.
- **Bootstrap target**: A host configuration under `bootstrap/targets/`, applied locally or through `mise bootstrap remote`.
- **Dev tool**: A binary needed to work on this repo. Pinned in `mise.toml`.
- **Host tool**: A binary reconciliation installs onto a machine for its own sake. Declared in a native capability or a Brewfile under `bootstrap/capabilities/mac-apps/`. `mise` and `uv` are host tools that development also happens to need.
- **Capability**: A unit of native host configuration, shared under `bootstrap/capabilities/` or owned by one target. It owns a thing that can be installed or configured, not a machine.
- **Role**: A retained Ansible unit under `ansible/roles/`, used only by work's remaining legacy consumers.
- **Docker stack**: A Compose project under `bootstrap/targets/pod042/containers/stacks/`, reconciled by native mise Compose resources.
- **TrueNAS**: Retired NAS platform; its apps and `local.truenas` collection appear only in migration history.
- **UniFi provider fork**: `thurstonsand/terraform-provider-unifi` that supplies controller fields absent upstream. Its release branch stays rebased on upstream, publishes multi-platform GitHub Releases, and enters OpenTofu through ansiblonomicon's verified filesystem-mirror installer.
- **Chezmoi source**: The `chezmoi/` tree retained for work's private templates, data, and cleanup. Personal hosts do not consume it.
- **SecretRef**: An `op://vault/item/field` pointer in `fnox.toml` or `fnox.<host>.toml`. Fnox resolves one host set for a consumer process.
- **Agent harness**: A coding agent runtime — Pi, Claude Code, Amp, Codex, OpenCode, Gemini. The native `agent-harness` capability reconciles their plugin catalogue; `agent-config` renders settings, instructions, and source assets for each runtime.
- **Pi**: My favorite AI agent harness. Extends through TypeScript **extensions** loaded straight from source, plus **packages** pulled from separate repos.
- **Amp**: My other favorite AI agent harness. Extends through TypeScript **plugins** (different from **Agent plugins**).
- **Agent plugin**: A directory under `agents/` holding a themed set of skills, installable by any harness configured in this repo.
- **Session recovery**: The shared library that lets an interrupted agent session be picked back up, with a common core and per-harness entry points.
- **Work machine**: The corporate laptop. Same repo, constrained by an Artifactory mirror that carries only a certain set of dependencies and versions, and cannot easily be extended.
- **pod042**: The NAS successor — plain Debian 13 on the old TrueNAS hardware.
- **OpenClaw**: pod042's predecessor. Sunsetting; treat any remaining reference as legacy and removeable.
- **Home Assistant**: An appliance managed outside the scope of this repo, aside from management of the VM itself via Incus. All other management is done through the `home-assistant` mcp.

## Unifi Networks

- **Bunker**: Infrastructure; Native, untagged
- **YoRHa**: Administrators
- **Lunar Tear**: Household and guests
- **Scanners**: Controllable devices
- **The Village**: IoT
- **Transporter**: VPN
