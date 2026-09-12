---
status: open
type: task
blocked-by: []
---

# Give pod042 sight of the client networks

## Question

pod042 is where an agent runs when Thurston is away from the house, so it is the only thing that can answer "what is actually happening on the network" while he is remote. Today it answers that for Bunker and, by accident, for Scanners: its switch port carries VLAN 40 tagged because the Home Assistant VM needs it. Lunar Tear and The Village are excluded from the port profile, so two unidentified Espressif boards sat on Lunar Tear for nine days and could not be probed from the one machine in the house capable of probing them.

Grant pod042, and only pod042, the reach to observe every client network except YoRHa. Thurston asked for this explicitly. It is a deliberate narrowing of an invariant, not drift.

## What this contradicts

[VLAN security redesign](13-vlan-security-redesign.md) made it an invariant that the infrastructure tier never initiates toward client tiers, because pod042 runs internet-reachable services and a compromised workload there must not pivot into the house. This ticket keeps the zone-level invariant and carves out one host.

## Why the obvious shape is wrong

The obvious shape is to trunk the VLANs to pod042's port and give the host an address on each. During the printer diagnosis on 2026-09-12 an agent did exactly that, holding `10.10.40.251/24` on `enp5s0.40` for roughly two hours. Measured on the live host, that address exposed more than it observed:

- `iptables -P FORWARD ACCEPT` with `net.ipv4.ip_forward = 1` and `rp_filter = 2` on `enp5s0`. Docker only installs `FORWARD DROP` when Docker itself enables forwarding; `/etc/sysctl.d/90-pod042-network.conf` gets there first, so the policy stays open. A client with a static route through that address reaches Bunker, the Docker bridges, and pod042-kvm, bypassing every zone policy.
- Wildcard listeners answer on any interface the host holds an address on: `sshd` on 22, Caddy on 80 and 443, Plex on 32400, Scrypted on 10081, 10443, and 11080. Caddy's `local_only` matcher allowlists the `.10`, `.20`, and `.30` networks, but the publicly served sites are served to whoever reaches 443. A Village appliance would get them with no Cloudflare Access in front.
- Traffic from a client to that address never touches the UDMP, so "the zone matrix already denies the return direction" is false at L2. The denial is a routing fact, not a host-firewall fact.

`enp5s0.40` also does not reach Home Assistant. It is the macvlan parent, and macvlan isolates parent from children by design, which is why `10.10.40.42` did not answer during the printer work.

## Shape

Terminate the client VLANs inside a dedicated network namespace that holds no services, no default route, and no path to the root namespace.

- Root namespace keeps `enp5s0.30`, `enp5s0.40`, and `enp5s0.50` as addressless VLAN subinterfaces with IPv6 disabled. `enp5s0.40` must stay in root because Incus parents its macvlan network on it. Disabling IPv6 on the parents is load-bearing: an addressless interface still gets a link-local address, and `sshd` and Caddy listen on `[::]`.
- A `probe` namespace holds one bridge-mode macvlan child per parent, each with its own locally administered MAC, a static address, a connected route, `ip_forward = 0`, no default route, and no veth to root. Bridge-mode macvlan is also the only thing that can reach the Home Assistant VM.
- The agent enters through a declared `ip netns exec probe` wrapper. Host-network containers, docker-proxy, sshd, and Tailscale never see these interfaces, and an agent that forgets the wrapper gets "network unreachable" rather than silently probing from the service host.

Three `unifi_client` records with fixed addresses name the probe identities, so the controller shows named clients rather than pod042 appearing to hop networks under one MAC.

## Work

- Fix the live drift first, as its own step. Confirm no `10.10.{30,40,50}` address exists in the root namespace and that no ad-hoc listener is bound. Declare `enp5s0.40` addressless with IPv6 off and assert it in `bootstrap/targets/pod042/network/check.py`.
- Declare `FORWARD` policy `DROP` in root. This is worth doing whether or not the rest of this ticket happens; Docker inserts its own bridge accepts and Tailscale advertises no routes.
- Build the read-only reach first: a skill wrapping the UniFi controller and NextDNS APIs, reusing `scripts/unifi_smoke.py`'s authentication and the fnox secrets already on the host. That answered the Espressif question on its own and covers most of "what is on the network" with no network change. It cannot do ARP, ICMP, port probes, mDNS browsing, or DHCP fingerprints, and The Village has no mDNS reflection at all, which is where the probe earns its place.
- Drop `lunar_tear` and `the_village` from `excluded_networkconf_ids` on the existing `unifi_port_profile.pod042` in `terraform/unifi/ports.tf`. It already serves only port 17, so no new profile is needed.
- Declare the parents, the namespace, and the wrapper in `bootstrap/targets/pod042/mise.network.toml`, ordered after the parents exist and without racing Incus over `enp5s0.40`.
- Add `nmap`, `tcpdump`, `arp-scan`, and `mdns-scan` to `bootstrap.packages`. Not `avahi-utils`: `avahi-browse` needs a daemon and D-Bus the namespace does not have.
- Extend `check.py`: parents addressless with IPv6 off, the namespace holding exactly three addresses and no default route, no client-VLAN address in root, `FORWARD` policy `DROP`.
- Write the exception next to the invariant in [VLAN security redesign](13-vlan-security-redesign.md): Bunker never initiates toward client tiers; pod042 carries a separate probe identity on each client VLAN that is not on Bunker and hosts no service.
- Write down the rule that keeps this from growing: no veth into `probe`, and no service ever gets a VLAN interface. Otherwise the exception becomes the zone-level allow ticket 13 rejected.

## Open decisions

1. Namespace, or plain interfaces plus a declared nftables file, or an Incus container. The nftables route is cheaper and closes the same findings, but it is a deny-list over a default that is open, and the two hours of undeclared `10.10.40.251` are the evidence that nobody notices when the default opens.
2. Whether the probe answers ICMP and ARP from client VLANs. Allowing it is reasonable; it is a named client.
3. Whether Plex should ever advertise into Lunar Tear for household discovery. That is a real feature request and deserves its own ticket, not a side effect of this one.

## Non-goal

This design does not contain a compromised agent. Root on pod042 can do anything, including entering the namespace or creating its own interfaces. What it contains is the blast radius of the host's services and of an agent's ordinary mistakes. Agent containment is Tailscale SSH and the relays, and lives elsewhere.

## Completion

pod042 can ping, port-probe, and browse mDNS on Lunar Tear and The Village from inside each segment, proven against a named client on each, and from the namespace rather than the host. YoRHa remains unreachable. No client VLAN can reach a pod042 service or route through it. The interfaces survive a reconcile, `check.py` fails if they drift, OpenTofu reports **No changes**, and the exception is written down next to the invariant it narrows.
