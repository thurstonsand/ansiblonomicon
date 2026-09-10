---
status: closed
type: grilling
blocked-by: [31]
claimed: T-01a0790a-aa41-7258-b0fd-c559a15e473a
---

# Host network desired state

## Question

Specify pod042's final network declaration under the completed trust-domain design: physical 2.5 GbE interface, Bunker access-port identity, DHCP reservation or static addressing, DNS, bridge requirements for Docker and Incus, forwarding, firewall ownership, MTU, boot-time failure behavior, and Wake-on-LAN through `pod042-kvm`. Pair WOL with a BIOS decision for power recovery after AC loss and state plainly what remains impossible without the GL-ATXPC board.

The old tagged bridge and macvlan topology is scheduled to retire, so treat it as migration evidence, not desired state. Close with link, routing, isolation, and reboot acceptance tests; then create a separate implementation ticket.

## Resolution

Grilled 2026-09-06 against the running Debian host and the clean live UniFi plan. Pod042 keeps its Intel I225-V (`enp5s0`) as an untagged 2.5 GbE Bunker endpoint at MTU 1500. Debian remains an `ifupdown` DHCP client; `auto` makes boot obtain its lease before declaring the network online so Docker receives working DNS after a cold start. OpenTofu owns MAC `a0:36:bc:28:37:41`, fixed address `10.10.10.42`, local name `pod042`, and the switch's existing Bunker access-port identity. Wi-Fi does not participate.

There is no host `br0`. Docker and Incus own disjoint private bridges and NAT; their platform tickets select exact collision-free CIDRs. The host-network capability owns IPv4 forwarding because both depend on it. Routed IPv6 remains disabled while physical link-local IPv6 remains harmlessly available.

Traffic enforcement stays at the layer that can identify it. UniFi owns inter-zone routing and admits YoRHa to Bunker plus Lunar Tear to pod042 TCP 80, 443, and 32400. Caddy owns hostname-level local policy. Docker and Incus own bridge mechanics; later host nftables rules are reserved for per-workload forwarding or egress controls that UniFi cannot identify. Internet HTTP reaches no router port: Cloudflare Access, where selected, precedes the outbound tunnel. Plex alone retains direct WAN TCP 32400.

Local and remote HTTP share hostnames and Caddy routes, not transport or authorization. Exact UniFi local records for each retained Bunker service point directly to `10.10.10.42`; wildcard DNS is rejected because it would capture externally hosted siblings such as Amp, CleanShot, and Nabu Casa. Local clients terminate TLS once at Caddy's host-published 443 listener. Public clients terminate TLS once at Cloudflare; the encrypted tunnel reaches cloudflared, which uses a private Docker network to Caddy's unencrypted, unpublished internal listener. Cloudflare Tunnel exposure remains explicit per service. Cloudflare Access governs remote authorization; UniFi and Caddy govern local authorization. Application routes are shared between both listeners without an HTTP-to-HTTPS loop.

Home Assistant is deferred to the out-of-scope smart-home rebuild. Its web UI could traverse Caddy from an Incus private address, but NAT would hide its identity as pod042, Bunker cannot initiate toward device networks, and mDNS does not cross that boundary. A real deployment must choose a tagged Scanners bridge or dedicated interface rather than weakening Bunker isolation now.

Power recovery is designed but its disruptive proof waits for a laptop-controlled handoff. Enable ASUS `Power On By PCI-E`, set `Restore AC Power Loss` to `Power On`, persist magic-packet WOL, and prove shutdown-to-WOL through `pod042-kvm`. Without GL-ATXPC or a controlled PDU, KVM cannot press power/reset or recover a hard freeze; that manual-recovery gap is accepted for now.

Acceptance requires a clean refreshed OpenTofu plan after apply; fixed address and exact local DNS from permitted clients; 2.5 Gb/s, MTU 1500, default route and resolver state after cold boot; YoRHa administration, Lunar Tear web/Plex access, blocked unapproved initiation, and no unexpected host listeners; private bridge egress without LAN identity; local Caddy TLS and tunnel-to-Caddy HTTP reaching one representative application; Plex's direct path; and laptop-controlled lease, reboot, WOL, and rollback checks. [Implement the pod042 host network](44-implement-host-network.md) owns execution.

## Acceptance amendment

On 2026-09-10 the user permanently removed further link-loss, cold-boot, firmware-power, and powered-off WOL drills from this home-lab acceptance boundary. Persistent interface WOL and delivery through the KVM's native WOL endpoint are proven. The ASUS power-recovery settings were not applied and are no longer a requirement; real failures will drive any later firmware change.
