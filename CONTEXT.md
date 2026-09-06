# Context

- **Ansiblonomicon**: This repo. The single declarative source for every machine I own — laptops, NAS, router, dev VM, and for the Cloudflare edge in front of them.
- **Host**: A machine this repo configures. Ansible-managed hosts have a playbook and inventory entry; mise hosts have a native mise bootstrap target under `bootstrap/targets/`.
- **Reconcile**: One host run bringing the machine to its declared state. The unit of applying change; always re-runnable, always safe to repeat.
- **Tag**: The unit of partial Ansible reconciliation.
- **Bootstrap target**: A host configuration under `bootstrap/targets/`, applied locally or through `mise bootstrap remote`. New host-state work migrates to this native mise model as its existing Ansible unit is touched.
- **Dev tool**: A binary needed to work on this repo. Pinned in `mise.toml`.
- **Host tool**: A binary reconciliation installs onto a machine for its own sake. Declared in the Brewfile or a role. `mise`, `uv`, and `chezmoi` are host tools that development also happens to need.
- **Role**: A unit of capability under `ansible/roles/`. A role owns a thing that can be installed or configured, not a machine that needs configuring.
- **Docker stack**: A group of containers defined by a compose template in `ansible/stacks/` and rendered onto TrueNAS.
- **TrueNAS app**: A catalog app declared in `truenas_apps` and applied through the middleware rather than Docker directly.
- **`local.truenas`**: The in-repo Ansible collection that speaks to TrueNAS middleware — VMs, datasets, shares, apps, scrub and SMART schedules.
- **UniFi provider fork**: `thurstonsand/terraform-provider-unifi` that supplies controller fields absent upstream. Its release branch stays rebased on upstream, publishes multi-platform GitHub Releases, and enters OpenTofu through ansiblonomicon's verified filesystem-mirror installer.
- **Chezmoi source**: The `chezmoi/` tree in this repo.
- **SecretRef**: An `op://vault/item/field` pointer in `fnox.toml` or `fnox.<host>.toml`. Fnox resolves one host set for a consumer process.
- **Agent harness**: A coding agent runtime — Pi, Claude Code, Amp, Codex, OpenCode, Gemini. Each has its own config shape; the `agent_harness` role reconciles one declaration across all of them.
- **Pi**: My favorite AI agent harness. Extends through TypeScript **extensions** loaded straight from source, plus **packages** pulled from separate repos.
- **Amp**: My other favorite AI agent harness. Extends through TypeScript **plugins** (different from **Agent plugins**).
- **Agent plugin**: A directory under `agents/` holding a themed set of skills, installable by any harness configured in this repo.
- **Session recovery**: The shared library that lets an interrupted agent session be picked back up, with a common core and per-harness entry points.
- **Work machine**: The corporate laptop. Same repo, constrained by an Artifactory mirror that carries only a certain set of dependencies and versions, and cannot easily be extended.
- **pod042**: The NAS successor — plain Debian 13 on the old TrueNAS hardware.
- **OpenClaw**: pod042's predecessor. Sunsetting; treat any remaining reference as legacy and removeable.

## Unifi Networks

- **Bunker**: Infrastructure; Native, untagged
- **YoRHa**: Administrators
- **Lunar Tear**: Household and guests
- **Scanners**: Controllable devices
- **The Village**: IoT
- **Transporter**: VPN
