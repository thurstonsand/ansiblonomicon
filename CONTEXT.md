# Context

- **Host**: A machine this repo configures. Its **bootstrap target** under `bootstrap/targets/` holds its configuration.
- **Reconcile**: One host run bringing the machine to its declared state.
- **Tag**: A selector for partial reconciliation of a host. Each tag selects a capability or one of its sections.
- **Dev tool**: A binary needed to work on this repo. Pinned in `mise.toml`.
- **Host tool**: A binary installed from reconciliation onto a machine for general use. Declared in a native capability or a Brewfile under `bootstrap/capabilities/mac-apps/`. `mise` and `uv` are host tools that development also happens to need.
- **Capability**: A unit of native host configuration, shared under `bootstrap/capabilities/` or owned by one target. It is a thing that can be installed or configured, not a machine.
- **Docker stack**: A Compose project reconciled by native mise Compose resources. General applications live under `bootstrap/targets/pod042/containers/stacks/`; the `observability` capability keeps its stack beside its collectors and parsers.
- **UniFi provider fork**: `thurstonsand/terraform-provider-unifi`, which supplies controller fields absent upstream. Its `release` branch stays rebased on upstream; `terraform/unifi/README.md` covers how it reaches OpenTofu.
- **Agent harness**: A coding agent runtime — Pi, Claude Code, Amp, Codex. The native `agent-harness` capability reconciles their plugin catalogue; `agent-config` renders settings, instructions, and source assets for each runtime.
- **Agent plugin**: A directory under `agents/` holding a themed set of skills, installable by any harness configured in this repo.
- **Home Assistant**: An appliance managed outside the scope of this repo, aside from management of the VM itself via Incus on pod042. All other management is done through the `home-assistant` mcp.

## Hosts

- **pod153**: The MacBook Pro, retired from desktop use into an always-on headless server beside pod042. Reconciled by `mise laptop`.
- **Work machine**: The corporate laptop, also reconciled by `mise laptop`. Same repo, constrained by an Artifactory mirror that carries only a certain set of dependencies and versions.
- **pod042**: The NAS — plain Debian 13 server. Reconciled by `mise pod042`.
- **cupertino**: pod153's Tart VM signed in to Messages, where imsgbus serves iMessage to Beeper and to agents. Reconciled from pod153 by `mise cupertino`; see `bootstrap/targets/cupertino/README.md`.
- **no9-type-s**: The Framework laptop's Omarchy side, the personal Omarchy laptop, dual-booting with eve. Reconciled by `mise omarchy`; read `bootstrap/targets/no9-type-s/README.md` before customizing it.
- **eve**: The Framework laptop's Windows side, dual-booting with Omarchy. Reconciled by `mise windows`; see `bootstrap/targets/eve/README.md`.
- **UDMP**: The home router. `mise udmp [--check|--update-mise]` reconciles its OS services from the remote inventory in `bootstrap/mise.toml`; its Network application resources are OpenTofu in `terraform/unifi/`.

## Unifi Networks

- **Bunker**: Infrastructure; Native, untagged
- **YoRHa**: Administrators
- **Lunar Tear**: Household and guests
- **Scanners**: Controllable devices
- **The Village**: IoT
- **Transporter**: VPN
