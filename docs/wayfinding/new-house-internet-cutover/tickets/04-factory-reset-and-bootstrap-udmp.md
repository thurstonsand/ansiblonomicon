---
status: closed
type: task
blocked-by: [3]
claimed: 01a05cfb-8dd1-7255-9615-e02b82b6956c
---

# Factory-reset and bootstrap the UDMP

## Question

Execute the approved first stage with the BGW620 still supplying Internet: cable the Mac directly, factory-reset the UDMP, complete console ownership, create the Local Access Only recovery administrator, enable local management, establish the designed Bunker and YoRHa networks, and prove wired YoRHa Internet through the BGW620. Keep every AP disconnected until old controller state is gone, then factory-reset and adopt exactly one AP and publish the new YoRHa SSID. Stop with a clean, locally recoverable router whose WAN still has the BGW620 as the known-good upstream.

## Execution record

- Archived encrypted pre-reset Network and system backups and verified decryption before removing the plaintext copies.
- Moved the BGW620 management LAN to `192.168.10.254/24`, preserving its guest-network reservation and a clean boundary from the UDMP's factory subnet.
- Isolated the old UniFi estate, factory-reset the UDMP, chose **Continue Without Backup**, and retained the vanilla console name `UDM Pro`.
- Created and verified the Local Access Only `recovery` Super Admin, enabled SSH, and stored both credentials in the existing `Ubiquiti Account` 1Password item.
- Converted the native LAN to untagged Bunker at `10.10.10.1/24` and created YoRHa VLAN 20 at `10.10.20.1/24`, each with DHCP `.100` through `.249` and IPv6 disabled.
- Upgraded the empty controller to zone-based firewalling. Created the Bunker and YoRHa zones plus the stateful `YoRHa to Bunker` allow and logged `Bunker to YoRHa` block policies.
- Added `terraform/unifi/` with `ubiquiti-community/unifi` pinned to 0.55.0 and an R2 backend. Imported both networks, both zones, and both policies, then conformed HCL to controller normalization until the targeted refreshed plan reported **No changes**. The native Bunker network imports with VLAN unset even though the UI displays VLAN 1; explicit `vlan = 1` produced a live diff and was rejected.
- Created and applied the Bunker access, YoRHa access, and infrastructure trunk profiles through OpenTofu. Applied port 1 as Bunker recovery and port 2 as YoRHa test; the controller API confirmed both assignments.
- Proved wired YoRHa on port 2 at 1 Gb/s: a lease in `10.10.20.100` through `.249`, gateway reachability, DNS through the UDMP, and an Internet request forced through Ethernet all passed.
- Disconnected only BGW Ethernet from port 9. Ethernet Internet failed as expected while a fresh browser session authenticated with the Local Access Only account at `https://10.10.20.1`; the authenticated Network dashboard loaded with port 9 still down. Reconnecting port 9 restored link, DNS, and Ethernet Internet at the first check, inside the five-minute gate.
- Reconnected the Pro Max 24 PoE uplink on switch SFP+ port 26 to UDMP port 11 at 10 Gb/s. Recovered the old device-SSH credential locally from the encrypted backup, factory-reset the switch with `syswrapper.sh restore-default`, adopted it without a firmware update, and assigned port 26 to the OpenTofu-owned Infrastructure Trunk profile.
- Assigned UDMP port 7 to Bunker Access, physically reset and adopted the Power Distribution Pro, and verified outlets 5 and 7 remained enabled and under load while the switch and UDMP stayed Online. Provider 0.55 cannot import an otherwise empty PDU device without a perpetual update, so the PDU and its outlet relays remain outside OpenTofu state.
- Reset one old-controller U7 Pro Max over SSH, adopted it without a firmware update, and isolated an unstable switch port during link acceptance: the same replacement cable negotiated only 100 Mb/s and flapped on port 24, then held 2.5 Gb/s full duplex on port 23. OpenTofu assigns port 23 to Infrastructure Trunk and leaves port 24 as Bunker Access pending later diagnostics.
- OpenTofu created the YoRHa WLAN. Network 10.5 dropped 6 GHz on initial creation as documented by the provider's known controller workaround; an imported in-place update then established 2.4, 5, and 6 GHz, WPA3 Personal without transition mode, PMF Required, and MLO. Provider 0.55 echoes the controller PSK into state after refresh; the user accepted access-controlled R2-state exposure in exchange for OpenTofu ownership, so the resource uses the normal sensitive passphrase field and no secret enters Git.
- Associated the Mac to YoRHa on 6 GHz channel 85 at 160 MHz using WPA3 Personal and 802.11ax, obtained a YoRHa lease, resolved DNS, and reached the Internet through Wi-Fi. MLO remains configured but this client cannot prove Wi-Fi 7 negotiation.

- Held the UDMP, Pro Max 24 PoE, Power Distribution Pro, U7 Pro Max, 2.5 Gb/s AP uplink, and a live YoRHa 6 GHz client continuously healthy for 606 seconds.
- Found the initial `Bunker to YoRHa` block matched every connection state and appeared before UniFi's generated stateful response allow, so it blocked replies to allowed YoRHa requests. OpenTofu now declares that policy as `CUSTOM [NEW]`, which blocks Bunker initiation without intercepting established return traffic.
- Proved the final direction contract with an ephemeral Bunker network namespace rather than relying on UniFi device management ACLs: YoRHa reached an HTTP listener in Bunker, a Bunker-originated TCP connection to the Mac failed, the allow counter increased from 7 to 13, and the named block counter increased from 7 to 9. Removed the namespace and both listeners immediately after the test.

The clean minimum UniFi estate is locally recoverable, declaratively converged, and stable behind the BGW620. Ticket 05 may move to WAS-110 preparation and fiber cutover.
