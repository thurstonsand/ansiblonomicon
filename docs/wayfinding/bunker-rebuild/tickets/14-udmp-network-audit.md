---
status: closed
type: research
blocked-by: []
---

# UDMP network audit

## Question

What does the home network actually look like today — VLANs, the devices in each, and the firewall rules between them — and which of it falls outside what the caddy-gateway model can cover?

The [Service runtime topology](05-service-runtime-topology.md) grill confirmed bridges + one caddy as the HTTPS gateway, with macvlan surviving only if real zone separation is demanded. That demand can only be assessed against the real network: inventory the UDMP's VLANs/networks, the devices homed in each, and every inter-VLAN firewall rule, then classify what each rule protects. Output: a research doc with the current-state map and an explicit list of anything that would still need per-container VLAN membership (macvlan) or other measures outside caddy's L7 scope — with the why per item.

Read-only against the UDMP. Feeds [VLAN security redesign](13-vlan-security-redesign.md).

## Resolution

Four LAN networks, live: Default untagged `192.168.1.0/24` (zone Internal), IoT vlan 2 `192.168.3.0/24`, External vlan 3 `192.168.5.0/24` (zone "Soft External"), Personal vlan 4 `192.168.6.0/24`. Every DHCP pool stops at `.224` and each NAS macvlan takes `.224/27` above it — the carve-out documented in `truenas.yml` holds exactly. Default reaches every tier unconditionally; every other tier is default-denied toward the rest, with 23 hand-cut custom policies on the zone-based firewall.

The finding that reframes the question: **the UDMP is currently the reverse proxy.** Caddy serves one static site; every other service is reached at its own container IP via a UDMP local-DNS record, and VLAN membership *is* the per-service access control. One caddy does not refine that model, it replaces it.

Nine of the 23 rules name a Docker macvlan MAC. Seven describe traffic between things that will all land on the bunker — `Overseerr => Arr Apps` (154k hits), `Overseerr => Plex` (28k), `Homepage -> Truenas`, plus the retiring scrypted/frigate pair — and simply dissolve. Two survive as host-to-host and get coarser: `External SSH Access` (cloudflared → udmp, openclaw) becomes *any* bunker container → those hosts. That loss of principal granularity is the honest cost of bridges, and no caddy feature recovers it, because caddy is not in the path of a container's outbound connection.

Only one thing genuinely cannot be expressed: **blast-radius containment for the internet-published set.** The External VLAN has no SSID, no DHCP client, no human device — it exists solely to quarantine seerr/ghost/anypod/cli-proxy-api/cloudflared. `remote_ip` is an ingress matcher; containment is egress. Options: accept it and place the bunker in a restricted tier, keep one macvlan attachment for the published stacks, or give them their own runtime boundary. Worth noting the counter-argument — `Internal → Soft External` is fully open today, so the wall already has the valuables on the wrong side.

Everything else classified out: mDNS reflection (avahi reflects unfiltered across `br0,br2,br3,br4`; a bridged container structurally cannot join a VLAN's multicast domain, but after HAOS and scrypted retire nothing needs to) and non-HTTP host ports (Plex 32400, gluetun peering, cloudflared's `ssh://` ingresses; MQTT retires). isponsorblocktv is free to move to a bridge — no rule names it and Personal → Internal is blocked, so it cannot be reaching the Apple TV locally today.

Three corrections to the record. The Plex forward is **32400→32400**, not 20460 — ticket 06 should be amended. `storj.thurstons.house` is not an exposure but an IP tracker: terraform reads it back as `home_ip` to build the Cloudflare Access "Home Network Bypass" policy, so ddclient's reprieve is right for a different reason. And the `trusted` and `iot` macvlan networks are both empty — two of the four exist only on paper.

For ticket 13, the segmentation problem is not the container VLANs. Default holds the router, NAS, HAOS, openclaw, the APs — and an Apple TV, three HomePods, a Nest Hub, three thermostats, a Denon receiver, and every Mac and watch, with open reach into every other tier. For ticket 15: 4 provably dead rules, 3 more that can never match because their device changed tier, 6 stale local-DNS records.

Full current-state map, every rule with its plain-language purpose, and the out-of-scope list with alternatives: [UDMP network audit](../research/udmp-network-audit.md).
