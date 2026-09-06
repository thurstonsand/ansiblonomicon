# UniFi OpenTofu

This directory owns the stable Network application configuration on the UDM Pro. It adopts a manually bootstrapped controller rather than pretending OpenTofu can create the credential or management path it needs.

## Ownership boundary

OpenTofu owns:

- Bunker, YoRHa, Lunar Tear, Scanners, and The Village networks, VLANs, DHCP, and IPv6 state
- Bunker, YoRHa, Lunar Tear, Scanners, and The Village firewall zones
- the named one-way zone policies
- the YoRHa WPA3 Personal SSID, including PMF, all three bands, and MLO
- the Lunar Tear and Scanners WPA2/WPA3 transition SSIDs on 2.4 and 5 GHz
- The Village WPA2 Personal SSID on 2.4 GHz
- name-only stable client records for explicitly retained devices
- reusable Bunker, YoRHa, Scanners, and The Village access profiles plus the infrastructure trunk profile
- stable device port assignments after physical adoption
- the disabled Internet 1 backup and primary WAS-110 DHCP WAN, including priority, failover mode, and the sensitive cloned MAC
- the `192.168.11.0/24` WAS-110 LCT interface route
- Gateway mDNS Proxy Custom mode for YoRHa, Lunar Tear, and Scanners, restricted to Apple AirPlay and HomeKit
- Network-device automatic update policy

Manual state remains manual because the provider cannot represent or safely round-trip it:

- console first-run ownership, Local Access Only recovery administration, and SSH
- the first native-LAN transition from `192.168.1.1` to Bunker at `10.10.10.1`
- physical reset and adoption of switches, power devices, and APs
- Power Distribution Pro outlet control; OpenTofu observes the device and its outlet state, but the provider excludes every `outlet_*` field from device updates
- the initial WAS-110 profile and service identity

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

The provider is pinned exactly to `github.com/thurstonsand/unifi` 0.56.0-ansiblonomicon.5, built from the `release` branch of the permanent [`terraform-provider-unifi`](https://github.com/thurstonsand/terraform-provider-unifi) fork. `provider.toml` records the checksums for macOS ARM64, Linux AMD64, and Linux ARM64. `mise run unifi:provider:install` verifies the matching GitHub Release archive and installs only its binary into OpenTofu's implied filesystem mirror; extra archive files change OpenTofu's directory hash. The fork is not published to a provider registry.

Shared R2 state moved from `registry.opentofu.org/ubiquiti-community/unifi` to the fork source once with `tofu state replace-provider`. Do not repeat that migration. The backend uses OpenTofu's native S3 lockfile; R2 rejects a competing conditional lock write. The encrypted pre-migration snapshot lives outside Git under `~/Documents/Network Backups/`.

Known sharp edges:

- The provider exposes both `unifi_network.firewall_zone_id` and `unifi_firewall_zone.network_ids`, which fight when both own membership. This module deliberately leaves `firewall_zone_id` unset; zones alone own membership here.
- policy ordering is read-only. Confirm named allows precede named/default blocks in the UI after import or creation.
- native Bunker may normalize VLAN 1 differently across controller versions. Conform HCL to a harmless imported representation; never apply a VLAN change merely to silence a plan.
- `unifi_wan` owns both WAN records and the sensitive cloned MAC. The UDM's `ethernet_override` blocks own only the `eth8`/WAN and `eth9`/WAN2 assignments; they do not force port 10 speed or duplex.
- `unifi_static_route` uses legacy routing endpoints. The imported WAS-110 route has converged without changes; keep requiring a zero-change refreshed plan before touching it.
- provider authentication does not support 2FA. It uses the Local Access Only recovery account from `fnox.toml`.
- Network may normalize the all-AP WLAN group into an explicit ID after creation. If the provider reports an inconsistent result, verify the live WLAN and state before importing or recreating it, clear the taint only after they match, and require a zero-change plan.
- The provider echoes controller PSKs into state after refresh. This module deliberately uses normal sensitive `passphrase` fields so plans converge; the user accepts R2-state exposure in exchange for OpenTofu ownership. State files remain excluded from Git.

## Commands

```sh
mise secrets:check
mise run unifi:provider:install
mise run unifi:init
mise run unifi:plan
mise run unifi:apply
mise run unifi:smoke
```

The R2 backend requires working Internet. Do not run OpenTofu during the fiber move, PON activation, DHCP diagnosis, or reboot-recovery test.

## First adoption

Never commit import IDs. Obtain them from the wired local controller session and pass them directly to `tofu import`.

Import the managed networks, zones, and named policies first. Then run a targeted refreshed plan against only those resources and make HCL conform to harmless controller normalization until it is empty. Apply nothing during this step.

Import the UDM Pro by its live MAC directly into remote state. Review the full plan and require that it contain only intended port-profile, port-assignment, and WLAN additions before apply.

After a provider or Network application update, require a clean `mise run unifi:plan` before changing the UI. Test representative packet flow only when the change touches zones, policies, or their ordering; the established YoRHa-to-Bunker allow and Bunker-to-YoRHa initiation block are the baseline witnesses, not a demand to exhaustively retest every rule. Confirm affected WLAN fields when Wi-Fi changes. The imported WAN records and UDM physical network-group assignments round-trip cleanly. Port 10 speed and duplex remain auto-negotiated and behavior-tested rather than configured.
