---
status: closed
type: grilling
blocked-by: [5]
---

# Agent platform on Proxmox

## Question

What replaces pod042 (the 4c/16G VM) on the new substrate, and what does full host resource sharing actually look like?

Direction from charting: LXC-style sharing — CPU/RAM limits as caps, not reservations, so compilation gets all 16 threads and free RAM instead of OOM-crashing at 2c/8G. Goals beyond sharing: fully unfettered access to anything in the system for the agent. Inspiration: Amp orbs — but durable rather than ephemeral, since there is one machine; if Proxmox makes orb-like ephemeral machines cheap to provision and destroy (templates, cloud-init LXC, `pct clone`), that is worth designing in.

To settle:

- One durable agent LXC vs a template + ephemeral clones vs both (durable home + disposable workers).
- What "unfettered" means concretely: docker socket access, `/mnt` visibility, Proxmox API access, nesting.
- What carries over from the pod042 map (self-management loop, secrets via `op` launcher role, Amp comms design) and what is superseded.
- Disposition of the pod042 map itself once this lands.

## Prework (2026-08-19, ahead of the grill)

Substrate is now decided ([ticket 05](05-service-runtime-topology.md)): plain Debian 13 + docker + **incus** — the "on Proxmox" in this ticket's title is historical. The platform question becomes: what does pod042's successor look like as incus instances?

**What pod042 is today** (live 4c/16G VM on TrueNAS, Debian 13, static 192.168.1.94; its map at `docs/wayfinding/pod042/`): self-management loop (systemd timer: repo checkout-reset → `poe pod042` → verify → one fingerprint-bounded `amp -x` repair with push-to-main autonomy); secrets via the minimal `op` service-account launcher role; Discord webhook as the Amp-independent dead-man's channel; Amp web/mobile threads as the conversational surface; docker work via `DOCKER_HOST=ssh://truenas` against the NAS daemon; NFS symmetric-path dataset for bind mounts.

**Transfers nearly unchanged**: the playbook + role set (sshd, shpool, sessions, agent_harness, chezmoi, op launcher), the self-management loop shape, the comms design, `pod042.thurstons.house` → whatever the successor answers to.

**Superseded by the new substrate**:
- Provisioning: `local.truenas.vm` → an incus profile + instance, declared from ansible. Debian images from images.linuxcontainers.org; `incus launch` makes template+clone ephemerals cheap (the orb-like path charting wanted).
- Resources: the 4c/16G reservation → caps (`limits.cpu`, `limits.memory` are ceilings on a shared host — the whole point of the move).
- Docker access: the daemon is now on the same machine. Three shapes to grill: bind the host docker socket into the instance (simplest, most "unfettered"), talk to it over the incus bridge, or `security.nesting=true` for a private docker inside the instance.
- Storage: 80G zvol → a `black-box/agents` dataset (already in ticket 10's layout) as incus storage/disk devices; `/mnt/ark`+`/mnt/black-box` visibility via disk devices with `shift=true` (VFS idmap — no manual uid mapping in incus 6.0).
- Network: static IP in the old trusted VLAN → the instance lives behind the bunker's single infra-tier port (ticket 13). Reachability shapes: incus bridged NIC (own MAC on infra — note this partially resurrects the per-workload-VLAN-presence pattern the topology killed for docker), or host-side proxy/ssh jump. Needs a deliberate call.

**Open pod042-map tickets whose fate this grill settles**: 08 sunset-openclaw (openclaw declared dead at ticket 13 sign-off — execution only), 09 build-pod042 (open/claimed; superseded or absorbed?), 11 arbitrary-directory runner, 13 detached session host. The pod042 map's disposition is already on this ticket's list.

## Resolution

Grilled 2026-08-19, two rounds plus a naming coda. Signed off.

**Names.** The Debian host itself takes the name **pod042** — `poe pod042` becomes the host reconcile; "bunker" survives only as this effort's codename. The durable agent instance is **pascal** — the peaceful machine who runs a village of workers. Workers are `w-<project>`.

**Shape: both, designed now.** One durable instance (pascal) as the ansiblonomicon home + management seat, plus an ansible-declared `agent-worker` profile and base image so `incus launch` yields per-project disposable workers in seconds (separate git clones per project — not cross-instance worktrees, which would force sharing the `.git` objects dir across boundaries).

**Pascal's trust envelope — all five grants**: host docker socket (manages the real stacks; docker-over-ssh retires), incus socket (spawns/destroys sibling workers — "that looks like a bug, spin up a box to chase it" is a tool call), `/mnt/ark` + `/mnt/black-box` disk devices with `shift=true`, root-capable ssh to the host (the self-management loop grows from "reconcile myself" to "reconcile pod042"), and `security.nesting` for a private inner docker. Rationale: each grant is host-root-equivalent once the first exists; the container boundary is for caps and clean reprovisioning, not containment. Restraint lives in the workers.

**Worker envelope (narrow)**: caps + nesting only — no host docker socket, no incus socket, no host ssh, no pool mounts by default; per-launch opt-ins. Secrets via the same scoped `op` service-account launcher role, read-only posture; workers report to pascal, which owns the Discord dead-man channel and the conversational surface. `--ephemeral` where it fits; otherwise pascal-managed destroy. Idle cost is near-zero (system containers are just their processes; caps are ceilings), so instances run until shut down — auto-spin-down on inactivity is a recorded nicety, not a requirement.

**Network: A+ — port-subdomain caddy route.** One caddy block, written once: `<port>.<instance>.thurstons.house` proxies to the instance's bridge IP on that port — any HTTP server any agent starts is instantly reachable with a name and HTTPS, workers included. Instances stay on the private incus bridge; ticket 13's single-access-port model holds. ssh + raw TCP via ProxyJump through the host (chezmoi-deployed ssh config). No hostname exists inside raw TCP — `postgres://` can't route by name; TLS-SNI routing via caddy-l4 noted as a someday-plugin path.

*Amendment (ticket 18 research)*: a TLS wildcard matches one label, so `*.thurstons.house` cannot cover `<port>.<instance>.thurstons.house` — the caddy route needs a per-instance wildcard cert (`*.pascal.thurstons.house`), practical via the existing DNS-01 setup but declared per instance. Raw TCP's real answer is WARP CIDR routing per [Raw TCP auto-expose](18-raw-tcp-auto-expose.md).

**Follow-up ticket seeded — external auto-expose**: wildcard cloudflared ingress (`*.<instance>.thurstons.house` → caddy) + wildcard Cloudflare Access app in `terraform/cloudflare` puts every agent port behind Access externally with zero per-server config; `cloudflared access tcp` covers raw TCP from outside.

**pod042 (the VM) dies; its map closes.** The existing VM tears down at cutover with the rest of TrueNAS. The pod042 map closes as superseded-by-bunker-rebuild: tickets 08 (sunset openclaw) and 09 (build) overtaken by events; 11 (runner tool) and 13 (detached session host) closed as unresolved ideas, re-charterable against the new platform if the need resurfaces. Salvaged as designs: the self-management loop, the `op` launcher role, the comms design. Execution item added to the map: purge openclaw and stale-pod042 references repo-wide.

