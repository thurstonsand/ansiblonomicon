---
name: operating-pod042
description: Operates the pod042 Debian NAS through native mise and Docker Compose. Use before changing its host state, services, containers, storage, monitoring, or network.
---

# Operating pod042

Treat this repository as pod042's desired state. Diagnose live state freely; make durable changes in the owning native mise capability and reconcile them.

## Entry points

- SSH host: `pod042` (`10.10.10.42` on the LAN, falling back to Cloudflare Access through `ssh-smart-proxy`).
- Tailscale: `pod042-ts`; forced Cloudflare path: `pod042-remote`.
- Recovery console: `pod042-kvm` locally or `pod042-kvm-ts` remotely, operated through `scripts/pod042_kvm.py` when host SSH is unavailable.
- Desired state: `bootstrap/targets/pod042/`.
- Reconciliation: `mise pod042 [capability] [--check]`, run on pod042 itself. It applies the current working tree, dirty or not.

Capabilities are registered in `scripts/pod042_reconcile.py` and `bootstrap/mise.toml`. Keep resource ownership disjoint. Read the capability's README and nearby ticket before changing storage, network, backup, or identity.

The network capability installs Tailscale but cannot enroll a new machine unattended. Its first reconcile intentionally fails the final network check until an operator runs `sudo tailscale up --hostname=pod042 --accept-dns=false --accept-routes=false --advertise-tags=tag:pod042 --ssh=true`, authorizes the printed URL, and reruns reconciliation. The declaration then enforces the direct, tagged Tailscale SSH posture without DNS, route acceptance, advertised routes, or an exit node. A fresh installation receives a new stable Tailscale address; update the network check and shared SSH template together.

### Orb access

In an Amp orb, run `scripts/with-pod042-access ssh -- <command>` to execute on pod042. Use `scripts/with-pod042-access lan -- <command>` for access to Bunker, Lunar Tear, Scanners, or The Village through the KVM's subnet routes. The generic form exposes the temporary Tailscale client without accepting those routes.

KVM API certificate verification is enabled by default. The appliance presents a self-signed certificate on its LAN and Tailscale addresses, so those paths require the explicit `--insecure` exception. For the convenience path, pass `--url https://pod042-kvm.thurstons.house` without that exception; the client requires verified HTTPS before loading Cloudflare Access credentials. Tailscale is the primary recovery path because it terminates on the independently powered KVM. Cloudflare's connector stops with pod042.

## Containers

- Compose sources: `bootstrap/targets/pod042/containers/stacks/<project>/`.
- Installed project definitions: `/etc/ansiblonomicon/containers/<project>/`, readable only by root because some are rendered with secrets.
- Durable application state: `/mnt/black-box/docker/<project>/`.
- Media and other large replaceable data: `/mnt/ark/media/`.
- Docker runtime, images, and layers stay on the boot SSD under Docker's defaults.
- Native `[bootstrap.compose]` resources own pull, build, recreation, health, orphan, and lifecycle policy. Compose owns dependencies and project-internal networks.

Read a project's definition from its compose source in the repo, never the installed copy. Reserve `sudo` for the case where you suspect the host has drifted from the declaration.

| Task | Command |
| --- | --- |
| All projects | `docker compose ls` |
| Project status | `docker ps --filter label=com.docker.compose.project=<project> --format 'table {{.Names}}\t{{.Status}}'` |
| All containers | `docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'` |
| Logs | `docker logs --since 30m <container>` |
| Inspect | `docker inspect <container>` |
| Execute | `docker exec -i <container> <command>` |
| Restart | `docker restart <container>` |

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
