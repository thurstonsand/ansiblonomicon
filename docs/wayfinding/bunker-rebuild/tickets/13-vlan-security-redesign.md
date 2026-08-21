---
status: closed
type: grilling
blocked-by: [14]
---

# VLAN security redesign

## Question

The move is the opportunity to rework the home network's segmentation from scratch: which VLANs exist, what lives in each, and what may talk to what — most notably isolating iot devices, and separating anything internet-exposed from personal devices.

Branches to settle:

- Tier inventory: today's tiers (trusted/iot/external/personal) grew organically around the NAS's macvlan networks. What is the right set when designed for the *house* — e.g. infrastructure (bunker, router, APs), personal, iot, guest, and whether a DMZ tier is warranted at all.
- The cloudflared calculus: tunnel-published services (ghost, seerr, anypod) have no inbound exposure — do they need zone separation, or is the true inbound surface only the direct-IP shortlist (`storj.thurstons.house`, plex direct, torrent peering)?
- Where the bunker host itself lives, and which VLANs may reach caddy:443 — the interlock with [Service runtime topology](05-service-runtime-topology.md).
- Enforcement split: UDMP firewall rules (L3, inter-VLAN) vs caddy `remote_ip` matchers (L7, per-service). What belongs where.
- How much of this is declarable: UniFi VLAN/firewall config vs what this repo can reconcile (the `udmp` playbook exists; scope of what it can own is fog).
- Migration path: every device in the house re-homes. Sequence relative to the physical move.

Output: the target tier model, per-tier firewall policy, and where each bunker service lands. Feeds the network half of [Service runtime topology](05-service-runtime-topology.md).

## Resolution

Grilled 2026-08-19, two rounds, grounded in the [UDMP network audit](14-udmp-network-audit.md). Signed off.

**Target model — six networks** (replacing today's four-plus-VPN):

1. **infra** — UDMP, APs, bunker, KVM, camera, honeypot (the UDMP's built-in threat-management decoy at .2). No mDNS. Invariant: never initiates toward client tiers. (openclaw dropped from the roster entirely — declared dead at sign-off, not coming back.)
2. **admin** — Thurston's Macs, iPhone, watches. One-way `admin → infra` and `admin → *` allow (today's Internal→* behavior, now with a tightening seam). Rationale: preserves escalation-prevention as a network guarantee while getting client devices off the router's L2.
3. **household** — everyone else's devices; guests too (no guest VLAN). Default-deny toward admin/infra; reaches discovery + caddy.
4. **discovery** — things humans cast/print/play to: Apple TV, HomePods, Google speakers, Chromecast, Denon, Remote Two, consoles (Xbox/PS5 forwards survive), the printer (moved from iot; the Allow Printer rule dies), future HA. mDNS reflected with admin+household only — deliberate reflection replaces today's unfiltered all-bridges reflector, which is both the segmentation hole and the source of the Apple-device setup pain.
5. **appliances** — the autonomous iot (thermostats, washer/dryer, oven, locks, robots, Tesla, Flo, Sense, Eight Sleep, TV, TRMNLs, UPS). Internet-only. Standing pattern for the smart-home map: `appliances → HA` on named ports when HA returns (today's MQTT hole, 42k hits, is the precedent).
6. **VPN** — WireGuard + Identity VPN carry over unchanged.

**Bunker containment: option A — per-host.** Single access port in infra; the NAS trunk, all four macvlan networks, and the External VLAN dissolve. All service HTTP behind one caddy (hostname routing on shared 443; per-tier `remote_ip` matchers); host ports only 80/443/32400. The audit's counterweight carried the argument: the old External-VLAN wall was one-way (`Internal → Soft External` fully open) and the published set has zero inbound LAN exposure (all cloudflared tunnels). Upgrade path if a hostile workload ever lands: per-container egress via host nftables, declared in this repo. UniFi's Object Oriented Networking cannot substitute — it keys on client MACs, and bridge containers share the bunker's.

**Rule fate** (from the audit): 7 container rules dissolve onto the bunker, 4 dead + 3 never-match rules deleted, 6 stale DNS records purged; per-container DNS replaced by one wildcard → bunker. The `External SSH Access` rule reduces to `bunker → udmp` (openclaw dead). isponsorblocktv to a plain bridge after a 5-minute confirm it's in cloud lounge-API mode (audit shows it cannot be using local discovery today).

Implementation lands via [UDMP declarative rebuild](15-udmp-declarative-rebuild.md) (fresh config; zone/OON authoring may also clear the historical enable-errors) and the [Cutover runbook](09-cutover-runbook.md).
