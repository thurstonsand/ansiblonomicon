# UniFi OpenTofu

This directory owns the stable Network application configuration on the UDM Pro. It adopts a manually bootstrapped controller rather than pretending OpenTofu can create the credential or management path it needs.

## Ownership boundary

OpenTofu owns:

- Bunker, YoRHa, Lunar Tear, Scanners, and The Village networks, VLANs, DHCP, IPv6 state, and mDNS participation
- Bunker, YoRHa, Lunar Tear, Scanners, and The Village firewall zones
- the named one-way zone policies
- the YoRHa WPA3 Personal SSID, including PMF, all three bands, and MLO
- the Lunar Tear and Scanners WPA2/WPA3 transition SSIDs on 2.4 and 5 GHz
- The Village WPA2 Personal SSID on 2.4 GHz
- name-only stable client records for explicitly retained devices
- reusable Bunker, YoRHa, Scanners, and The Village access profiles plus the infrastructure trunk profile
- stable device port assignments after physical adoption

Manual state remains manual because the provider cannot represent or safely round-trip it:

- console first-run ownership, Local Access Only recovery administration, and SSH
- the first native-LAN transition from `192.168.1.1` to Bunker at `10.10.10.1`
- physical reset and adoption of switches, power devices, and APs
- the Power Distribution Pro resource and outlet relays; provider 0.55.0 produces a perpetual device update even from an empty imported resource, and an apply must never risk cycling the gateway or switch outlets
- WAN physical-port roles, DHCP priority/failover, the BGW620 MAC clone, and port 10's forced 10 Gb/s
- the initial WAS-110 profile and service identity
- the `192.168.11.0/24` WAS-110 interface route until an import proves that Network 10.5's Policy Table representation round-trips through the provider's legacy static-route API
- Gateway mDNS Proxy Custom mode and predefined service filters

The live secret values and controller object IDs belong in 1Password and remote state, never HCL or this README.

## Bootstrap record

The controller was factory-reset and bootstrapped behind the BGW620 on UDM port 9. The unavoidable manual configuration is:

- console name `UDM Pro`
- owner: UI cloud account
- recovery administrator: Local Access Only, Super Admin, credentials in the `Ubiquiti Account` 1Password item
- console SSH: enabled, password in the same item
- Bunker: native untagged, `10.10.10.1/24`, DHCP `.100` through `.249`, automatic gateway/DNS, IPv6 disabled; the UI displays VLAN 1 while the API stores VLAN unset
- YoRHa: VLAN 20, `10.10.20.1/24`, DHCP `.100` through `.249`, automatic gateway/DNS, IPv6 disabled
- Lunar Tear: VLAN 30, `10.10.30.1/24`, DHCP `.100` through `.249`, automatic gateway/DNS, IPv6 disabled
- Scanners: VLAN 40, `10.10.40.1/24`, DHCP `.100` through `.249`, automatic gateway/DNS, IPv6 disabled
- The Village: VLAN 50, `10.10.50.1/24`, DHCP `.100` through `.249`, automatic gateway/DNS, IPv6 disabled
- zone firewall upgraded from the empty legacy ruleset before custom policy creation
- YoRHa may initiate toward Bunker, Lunar Tear, Scanners, and The Village, with automatic return traffic
- Lunar Tear may initiate toward Scanners, with automatic return traffic
- Bunker initiation toward YoRHa has an explicit logged block; the zone matrix denies other unapproved inter-zone initiation
- Gateway mDNS Proxy uses Custom mode for YoRHa, Lunar Tear, and Scanners only; Bunker and The Village remain excluded. Service scope contains only the predefined Apple AirPlay and HomeKit groups.

The full physical cutover and rollback gates live in [`docs/wayfinding/new-house-internet-cutover/tickets/03-cutover-safety-gates.md`](../../docs/wayfinding/new-house-internet-cutover/tickets/03-cutover-safety-gates.md).

## Provider constraints

The provider is pinned exactly to `ubiquiti-community/unifi` 0.55.0. It is the current provider that exposes Network 10.x zone resources plus 6 GHz and MLO WLAN fields. Do not loosen the pin casually.

Known sharp edges:

- Newer provider docs expose both `unifi_network.firewall_zone_id` and `unifi_firewall_zone.network_ids`, which fight when both own membership. The pinned 0.55.0 network schema does not expose the first field; zones alone own membership here.
- policy ordering is read-only. Confirm named allows precede named/default blocks in the UI after import or creation.
- native Bunker may normalize VLAN 1 differently across controller versions. Conform HCL to a harmless imported representation; never apply a VLAN change merely to silence a plan.
- `unifi_wan` cannot store the cloned MAC value or bind a WAN to a physical port. Never import either WAN.
- `unifi_static_route` uses legacy routing endpoints. Keep the WAS-110 route manual unless a tested import produces a zero-change plan.
- provider authentication does not support 2FA. It uses the Local Access Only recovery account from `.secrets.jsonc`.
- Provider 0.55.0 may report an inconsistent result after creating a WLAN because Network normalizes the all-AP group into an explicit ID. The object and state can still exist; verify the live WLAN and state before importing or recreating it, clear the taint only after they match, and require a zero-change plan.
- Provider 0.55.0 echoes controller PSKs into state after refresh. This module deliberately uses normal sensitive `passphrase` fields so plans converge; the user accepts R2-state exposure in exchange for OpenTofu ownership. State files remain excluded from Git.

## Commands

```sh
mise run secrets:init
mise run unifi:init
mise run unifi:plan
mise run unifi:apply
```

The R2 backend requires working Internet. Do not run OpenTofu during the fiber move, PON activation, DHCP diagnosis, or reboot-recovery test.

## First adoption

Never commit import IDs. Obtain them from the wired local controller session and pass them directly to `tofu import`.

Import the managed networks, zones, and named policies first. Then run a targeted refreshed plan against only those resources and make HCL conform to harmless controller normalization until it is empty. Apply nothing during this step.

Import the UDM Pro by its live MAC directly into remote state. Review the full plan and require that it contain only intended port-profile, port-assignment, and WLAN additions before apply.

After a provider or Network application update, require a clean `mise run unifi:plan` before changing the UI. Test representative packet flow only when the change touches zones, policies, or their ordering; the established YoRHa-to-Bunker allow and Bunker-to-YoRHa initiation block are the baseline witnesses, not a demand to exhaustively retest every rule. Confirm affected WLAN fields when Wi-Fi changes. WAN and WAS-110 route resources are intentionally absent, so OpenTofu must never propose drift for them.
