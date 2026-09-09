---
name: operating-pod042
description: Operates the pod042 Debian NAS through native mise and Docker Compose. Use before changing its host state, services, containers, storage, monitoring, or network.
---

# Operating pod042

Treat this repository as pod042's desired state. Diagnose live state freely; make durable changes in the owning native mise capability and reconcile them.

## Entry points

- SSH host: `pod042` (`10.10.10.42`).
- Recovery console: `pod042-kvm` (`10.10.10.34`), operated through `scripts/pod042_kvm.py` when host SSH is unavailable.
- Desired state: `bootstrap/targets/pod042/`.
- Guarded reconciliation: `mise pod042 [capability] [--check]` from another host; local execution on pod042 uses the same declaration and may intentionally apply the current working tree.
- The remote path requires clean, pushed, matching revisions. Do not bypass that guard.
- The remaining `ansible/stacks/`, pod042 inventory, and Ansible roles are migration evidence, not deployment authority.

Capabilities are registered in `scripts/pod042_reconcile.py` and `bootstrap/mise.toml`. Keep resource ownership disjoint. Read the capability's README and nearby ticket before changing storage, network, backup, or identity.

## Containers

- Compose sources: `bootstrap/targets/pod042/containers/stacks/<project>/`.
- Installed project definitions: `/etc/ansiblonomicon/containers/<project>/`.
- Durable application state: `/mnt/black-box/docker/<project>/`.
- Media and other large replaceable data: `/mnt/ark/media/`.
- Docker runtime, images, and layers stay on the boot SSD under Docker's defaults.
- Native `[bootstrap.compose]` resources own pull, build, recreation, health, orphan, and lifecycle policy. Compose owns dependencies and project-internal networks.

Use direct Docker commands for inspection and reversible diagnosis. Prefix them with `ssh pod042` when operating remotely:

| Task | Command |
| --- | --- |
| Project status | `docker compose -p <project> -f /etc/ansiblonomicon/containers/<project>/compose.yaml ps` |
| All containers | `docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'` |
| Project logs | `docker compose -p <project> -f /etc/ansiblonomicon/containers/<project>/compose.yaml logs --since 30m` |
| Inspect | `docker inspect <container>` |
| Execute | `docker exec -i <container> <command>` |

Do not edit installed definitions or `.env` files. Change the source declaration, run a focused check, then reconcile the `containers` capability. A manual container restart is diagnostic or immediate recovery only; reflect any enduring fix in Compose.

Services normally use private Docker bridges. Caddy is the only general ingress path. Plex additionally publishes 32400. The torrent project's qBittorrent and MAM services share Gluetun's network namespace; its Compose-owned repair service recreates them after Gluetun restarts or replacements.

## Secrets

Secrets are declared in `fnox.toml` and `fnox.pod042.toml`. Reconciliation resolves only the capability's named secrets and renders private consumer files where required. Use `scripts/fnox-host get NAME` or `exec --secret NAME -- COMMAND` when an operation needs a credential; never print, source, or persist broad secret sets.

The retained pod042 service-account token provides unattended Agent-vault access. Installing or rotating it is the separate attended `mise pod042:install-service-token` operation.

## Safety boundaries

- Read `bootstrap/targets/pod042/datasets/README.md` before changing datasets or migration state.
- Never write beneath an absent `/mnt/black-box/docker` or `/mnt/ark/media` mount.
- Do not recursively change imported ownership. Apply ownership only to the exact paths a consumer owns.
- Use native `state = "absent"` to retire managed state when propagation matters; remove the declaration after it converges away.
- Do not run broad Docker prune commands or delete bind-mounted application data without explicit approval.
- Reboots, link changes, firmware changes, pool mutations, and WOL tests are disruptive. Preserve independent KVM access and obtain approval first.
