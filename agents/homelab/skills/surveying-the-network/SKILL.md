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

1. `clients --unnamed` to get its address, MAC, VLAN, vendor OUI, and signal. The OUI alone often settles it; an Espressif OUI means an ESP32 microcontroller, so no Apple product and no full computer.
2. `traffic <address> --window -30d`. A vendor's own domain names the device outright. A bare AWS IoT Core or Alibaba IoT endpoint means small-vendor firmware and identifies only the manufacturer's cloud account.
3. Compare `first_seen` against the other clients. Devices that arrived together were installed together.
4. Only then reach for the segment, from pod042's probe namespace. Never give the host itself an address on a client VLAN; every wildcard listener it has would answer there.

## Probing a segment

pod042 terminates each client VLAN inside a network namespace that holds no service, no default route and no path back to the host. Interfaces are named for their networks.

```sh
sudo -n net-probe ip -br address                          # yorha, lunar-tear, scanners, village
sudo -n net-probe ping -c2 10.10.40.187
sudo -n net-probe arp-scan --interface=village --localnet  # what is actually on a segment
sudo -n net-probe nmap -Pn -p 80,443 10.10.30.0/24
sudo -n net-probe tcpdump -ni yorha udp port 5353          # watch discovery from inside a VLAN
```

This is the only supported route onto those segments, and the reason it exists is that discovery faults are invisible from outside the segment they happen on. Without the wrapper the command runs in the root namespace and reports "network unreachable" rather than probing from the service host. Each leg is a named client in the controller, so the segment's traffic is attributable.

`[randomized]` on a client marks a locally administered MAC, which is Apple's private Wi-Fi address. Set to Fixed it is stable for that network forever; set to Rotating it changes every two weeks. A name record against a rotating address will go stale.

## Naming

Every device of Thurston's carries a name-only `unifi_client` record in `terraform/unifi/clients.tf`, whatever network it sits on. Other people's devices, which in practice means most of Lunar Tear, are deliberately unnamed. Add a name with a resource, never in the controller UI, and reserve an address only when something needs one.
