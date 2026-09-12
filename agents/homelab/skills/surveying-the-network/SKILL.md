---
name: surveying-the-network
description: Answers what is attached to the house network, where it sits, and what it resolves, without touching the segment. Use when identifying an unknown device, auditing client names, or checking whether something is online.
---

# Surveying the network

Two read-only sources answer most questions about the house network without any access to the segment a device sits on. The UniFi controller knows what is attached, on which VLAN, and how its radio is behaving. NextDNS knows what each device resolves, and names devices it recognises.

Run everything from the repository root. Credentials resolve through fnox; never read them yourself.

```sh
mise run network:survey -- clients                  # what is attached, by network
mise run network:survey -- clients --history        # include devices seen but now offline
mise run network:survey -- clients --unnamed        # only clients with no controller name
mise run network:survey -- devices                  # adopted UniFi hardware
mise run network:survey -- traffic 10.10.40.187     # what one address resolves
mise run network:survey -- traffic 10.10.40.187 --window -30d
mise run network:survey -- resolvers                # devices NextDNS has seen, by volume
```

## Identifying an unknown device

Work in this order. Each step is cheaper than the next and usually enough.

1. `clients --unnamed` to get its address, VLAN, vendor OUI, and signal. The OUI alone often settles it; an Espressif OUI means an ESP32 microcontroller, so no Apple product and no full computer.
2. `traffic <address> --window -30d`. A vendor's own domain names the device outright. A bare AWS IoT Core or Alibaba IoT endpoint means small-vendor firmware and identifies only the manufacturer's cloud account.
3. Compare `first_seen` against the other clients. Devices that arrived together were installed together.
4. Only then reach for the segment. Bunker cannot initiate toward the client VLANs, so an L2 probe needs the work in [ticket 50](../../../../docs/wayfinding/bunker-rebuild/tickets/50-pod042-network-observability.md). Do not create ad-hoc VLAN interfaces on pod042 to get around this; an address on a client VLAN exposes every wildcard listener the host has.

`[randomized]` on a client marks a locally administered MAC, which is Apple's private Wi-Fi address. Set to Fixed it is stable for that network forever; set to Rotating it changes every two weeks. A name record against a rotating address will go stale.

## Naming

Every device of Thurston's carries a name-only `unifi_client` record in `terraform/unifi/clients.tf`, whatever network it sits on. Other people's devices, which in practice means most of Lunar Tear, are deliberately unnamed. Add a name with a resource, never in the controller UI, and reserve an address only when something needs one.
