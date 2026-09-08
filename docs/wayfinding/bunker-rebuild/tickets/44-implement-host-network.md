---
status: open
type: implementation
blocked-by: [36]
claimed: T-01a0790a-aa41-7258-b0fd-c559a15e473a
---

# Implement the pod042 host network

## Objective

Implement the accepted [Host network desired state](36-host-network-desired-state.md): declare pod042's physical network and forwarding through native mise, give it its OpenTofu-owned Bunker identity at `10.10.10.42`, add the accepted UniFi ingress, and establish the DNS and proxy ownership contracts consumed by later service deployments.

## Execution boundary

Work from the running pod042 host without invoking its retired Ansible playbook. Preserve local and remote native reconciliation, serial failure, and the guarded checkout contract. Do not install Docker, Incus, Caddy, cloudflared, Plex, or Home Assistant here; their tickets own runtime networks and application listeners. Exact local service records land with retained services so no name points at an absent Caddy route.

The current Amp thread runs on pod042 at its DHCP address. Code, tests, plans, and nondisruptive state may be completed here. Do not force DHCP renewal, change the live address, reboot, power off, alter firmware, or test WOL until control has handed off to the laptop. Treat the UniFi reservation as potentially disruptive even if the controller normally leaves the current lease intact.

## Completion evidence

- [x] Native mise owns the minimal `ifupdown` declaration, forwarding policy, retired network state, and checks for the intended physical interface, MTU, address source, routes, resolver, Wi-Fi exclusion, and unexpected bridges.
- [x] OpenTofu owns pod042's MAC, fixed address, local name, existing Bunker access port, and the accepted Lunar Tear destination-and-port policy; a refreshed plan is reviewed before apply and clean afterward.
- [x] Repository checks pass without secret leakage or an unintended network mutation.
- [x] From the laptop, change the lease to `10.10.10.42` with a tested rollback path and prove local/remote reconciliation reconnects.
- [ ] Prove permitted and denied inter-zone flows, link loss/recovery, a cold boot, firmware power recovery, and shutdown-to-WOL through `pod042-kvm`.
- [ ] Later representative Docker and Incus acceptance proves private-bridge egress and the local-Caddy/tunnel-Caddy routes without adding a host bridge.

## Implementation state

Laptop-controlled network cutover completed 2026-09-07. Native mise installed `ethtool` and now owns `ifupdown` DHCP, MTU 1500, persistent magic-packet WOL, IPv4 forwarding, disabled IPv6 forwarding, and retirement of the old bridge files. Pod042 renewed from its temporary `10.10.10.187` lease to reserved `10.10.10.42` under a timed `.187` rescue, reconnected on the fifth probe, and cancelled the rescue only after direct readback. The live verifier passes with one dynamic IPv4 address, one default route through `10.10.10.1`, the expected resolver, 2.5 Gb/s carrier, WOL `g`, no host bridge, unaddressed Wi-Fi, and no global IPv6. Both laptop-driven and host-local native checks report 16 unchanged resources and pass.

OpenTofu applied pod042's client reservation/local name and the Lunar Tear TCP policy as exactly two creates, then returned a clean plan. Controller attachment data corrected the original port assumption: the Pro Max 24 PoE's 2.5 GbE block is ports 17–24, and pod042 is physically connected to port 17 rather than port 24. OpenTofu now assigns the `pod042` name and Bunker access profile to port 17. Because the provider retained the removed port-24 override as unmanaged controller state, one authenticated controller PUT removed only that stale entry. Readback shows port 17 up at 2.5 Gb/s with MAC `a0:36:bc:28:37:41`, address `.42`, and the Bunker profile; port 24 is unassigned/default and down; the refreshed plan remains clean.

Policy acceptance used temporary listeners on ports 80, 443, and 32400 and removed them afterward. YoRHa reached SSH and all three service ports. The laptop then joined Lunar Tear at `10.10.30.182`; local DNS returned `.42`, all three declared service ports connected, and SSH port 22 timed out. The laptop returned to YoRHa at `10.10.20.110`; readback showed no temporary units and no new public listener. `pod042-kvm` independently reaches `.42` and provides `ether-wake`, but authenticated KVM API/video access timed out awaiting 1Password authorization. Link loss/recovery, reboot/cold boot, firmware settings, and shutdown-to-WOL therefore remain open and unattempted.

Docker acceptance now proves bridge egress through the host, VPN egress through Gluetun, and local Caddy routing into shared private service aliases without adding a host bridge. Incus acceptance and end-to-end client/tunnel checks remain open.

Focused Python lint, formatting, type checking, 79 tests, OpenTofu formatting and validation, and repository whitespace checks pass. The full repository check reaches the unrelated existing Amp/Pi TypeScript environment failures: Amp resolves the placeholder `tsc` package because TypeScript is unavailable, while Pi's installed TUI package lacks the `TuiMouseEvent` exports expected by `codexctl`.
