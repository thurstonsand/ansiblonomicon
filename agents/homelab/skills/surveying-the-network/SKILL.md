---
name: surveying-the-network
description: Inspects the house network, including direct probes across VLANs, and power-cycles UniFi-managed endpoints. Use for device identification, connectivity, discovery faults, or recovery.
---

# Surveying the network

Use `net-probe` whenever the answer depends on connecting directly to a device on a client VLAN. It enters that segment from pod042's isolated probe namespace; a command run from the host namespace cannot establish reachability.

For indirect inspection, the UniFi controller knows what is attached, on which VLAN, and how its radio is behaving. NextDNS knows what each device resolves, and names devices it recognises. A separate command power-cycles one explicitly named UniFi-managed power endpoint.

Run everything from the repository root. Credentials resolve through fnox; never read them yourself.

On pod042, run the commands below directly. From an orb or another host, execute them on pod042 through the Tailscale helper:

```sh
agents/homelab/skills/operating-pod042/scripts/with-pod042-access ssh -- \
  bash -lc 'cd /home/thurstonsand/code/ansiblonomicon && mise run network:survey -- clients'
```

```sh
mise run network:survey -- clients                  # what is attached, by network
mise run network:survey -- clients --history        # include devices seen but now offline
mise run network:survey -- clients --unnamed        # only clients with no controller name
mise run network:survey -- devices                  # adopted UniFi hardware
mise run network:survey -- traffic 10.10.40.187     # what one address resolves
mise run network:survey -- traffic 10.10.40.187 --window -30d
mise run network:survey -- resolvers                # devices NextDNS has seen, by volume
```

## Power cycling a device

After the user explicitly approves the interruption, name the adopted UniFi device and its PDU outlet or PoE port exactly. The command verifies that the controller device is online and that the selected endpoint currently supplies power. It cycles PoE through UniFi's device command. UniFi's nominal PDU cycle command leaves the PDU Pro's USB-C outlets without power while falsely reporting the relay as on, so PDU outlets instead use explicit relay provisioning: wait until off is applied, hold a true five seconds, restore power, and wait until on is applied.

```sh
mise run network:power-cycle -- "USP PDU Pro" 1    # Hue Bridge Pro on USB outlet 1
```

Use the PDU outlet or switch port that physically powers the target, not the target client's own name or address. Verify that the client and its service recover afterward.

## Identifying an unknown device

Work in this order. Each step is cheaper than the next and usually enough.

1. `clients --unnamed` to get its address, MAC, VLAN, vendor OUI, and signal. The OUI alone often settles it; an Espressif OUI means an ESP32 microcontroller, so no Apple product and no full computer.
2. `traffic <address> --window -30d`. A vendor's own domain names the device outright. A bare AWS IoT Core or Alibaba IoT endpoint means small-vendor firmware and identifies only the manufacturer's cloud account.
3. Compare `first_seen` against the other clients. Devices that arrived together were installed together.
4. Only then reach for the segment, from pod042's probe namespace. Never give the host itself an address on a client VLAN; every wildcard listener it has would answer there.

## Probing a segment

pod042 terminates each client VLAN inside a network namespace that holds no service, no default route and no path back to the host. Interfaces are named for their networks.

From an orb or another host, run these through the same helper's `ssh --` mode.

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
