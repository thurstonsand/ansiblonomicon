---
status: closed
type: grilling
blocked-by: [13]
---

# Service runtime topology

## Question

Where do the docker stacks live on Proxmox, and how does the network map across?

Branches to settle:

- Runtime placement: docker inside one LXC vs a docker VM vs docker on the PVE host directly (works, community-frowned) vs per-service LXCs. Weigh: `/dev/dri` sharing for Plex/QuickSync, bind mounts into `/mnt/{capacity,performance}` datasets, upgrade blast radius, how `poe` reconciliation reaches the daemon.
- Network: today's macvlan tiers (`lan:` in group_vars — trusted/iot/external/personal with static IPs) vs Proxmox bridges/VLANs. What do caddy, cloudflared, homepage, and the arr stack actually need?
- Plex lands where QuickSync stays shared (container/LXC, not a VM).
- Which stacks survive as-is: anypod, arr-apps, caddy, cli-proxy-api, cloudflared, ddclient, ghost, homepage, isponsorblocktv, torrent, watchtower (scrypted retires).

The answer shapes [Agent platform on Proxmox](07-agent-platform-on-proxmox.md) and the DNS/domain fog.

## Resolution

Grilled 2026-08-19, three rounds. All parts settled:

- **Substrate: plain Debian 13 + docker + incus.** Not Proxmox. Docker runs on its supported platform with zero hypervisor entanglement; incus (the community continuation of LXD, first-class in Debian 13's repos at 6.0 LTS) provides ticket 07's agent platform — system containers with caps-not-reservations, orb-like `incus launch` ephemerals, profiles declared from ansible — and covers the occasional-VM case through the same API (KVM). Research (research/docker-runtime-on-proxmox.md) showed Proxmox officially discourages both viable docker placements; its remaining value (web UI, vzdump) was outweighed by a permanent upgrade asterisk on the machine that owns all the data. vzdump was hollow here anyway — bind-mounted datasets are excluded from it by design. Rejected along the way: docker-in-LXC (mapping tax, unsupported seams), VM (QuickSync), Omarchy (desktop Arch, no server story), NixOS (competes with the repo's founding ethos).
- **Recovery story**: netinst + playbook — the same reinstall-plus-reconcile guarantee as every other host.

Earlier rounds settled:

- **Network shape (confirmed, conditional)**: docker bridges + one caddy as the HTTPS gateway — per-hostname routing, DNS-01 certs (already configured in the caddy stack), `remote_ip` matchers for per-VLAN L7 control, wildcard DNS; containers publish no host ports. Port contention dissolves. Host ports remaining: caddy 80/443 and plex 32400 only — the [UDMP audit](14-udmp-network-audit.md) corrected two assumptions: torrent peering arrives through Mullvad inside gluetun's namespace (no forward), and `storj.thurstons.house` is a DNS record feeding Cloudflare Access's home-IP bypass, not a listener (ddclient's reprieve stands, for that reason). macvlan survives only for whatever [VLAN security redesign](13-vlan-security-redesign.md) proves needs true zone separation — scoped by the [UDMP network audit](14-udmp-network-audit.md). `lan:` survives as the name book.
- **Roster**: all 11 stacks + plex carry over. ddclient reprieved — `storj.thurstons.house` is still used for other true-IP exposure beyond the retiring storj node.
- The substrate deliberation trail lives in the resolution above; the interim wait-on-13 sequencing was honored and 13's model (bunker on one access port in infra) is what this topology plugs into.
