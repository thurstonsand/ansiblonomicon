---
status: closed
type: task
blocked-by: [5]
---

# Verify direct Internet service

## Question

Prove the destination from the user-facing seams: a wired YoRHa client receives DHCP and reaches the Internet; the WAS-110 is O5 and reachable at `192.168.11.1`; the UDMP holds a public IPv4 lease directly from AT&T; a speed test reaches the expected service tier; and a deliberate UDMP reboot restores Internet without manual repair. Record observed evidence and failures. The BGW620 may leave immediate rollback duty only after every selected check passes.

## Execution record

- With port 9 physically disconnected, confirmed port 10 at 10 Gb/s full duplex, a non-private and non-CGNAT IPv4 lease, WAN health, five of five wired pings to `1.1.1.1`, gateway DNS answers, HTTPS 200, and LCT HTTPS 200.
- Corrected the BSD/macOS shorthand trap in ticket 03: `ping 1.1.1` addresses `1.1.0.1`, so the intended acceptance target is `1.1.1.1`.
- Ran the direct gateway speed test at 5.10 Gbps down and 5.26 Gbps up. Both exceeded the 80-percent thresholds of 4.18 Gbps down and 4.27 Gbps up.
- Began the 600-packet stability hold, then stopped it at the user's direction. The user explicitly waived that selected gate and chose to proceed; it is not recorded as passed.
- Issued the one permitted UDMP reboot with port 9 disconnected and made no recovery changes during the full 15-minute wait. The gateway returned with uptime consistent with that reboot.
- Reauthenticated through a fresh Local Recovery login after the reboot. The UDMP, public lease, port 10 10 Gb/s full-duplex link, directly scoped LCT route, O5.1 state, extended VLAN entries, and wired IP, DNS, HTTPS, and LCT checks all passed.
- Post-reboot optics remained healthy at Rx `-15.56 dBm` and Tx `6.34 dBm`, with no LOS/LODS line, two ME 84 entries, one ME 171 entry, and no fake-O5 marker.
- The shorter post-reboot gateway speed test reached 5.05 Gbps down and 5.25 Gbps up.
- Added the newly requested Lunar Tear household network as VLAN 30 at `10.10.30.0/24`, its own firewall zone, and a 2.4/5 GHz WPA2/WPA3 transition WLAN. Stored the requested credential in 1Password and R2 state only. A real client received Lunar Tear DHCP, resolved gateway DNS, and reached the Internet; an ephemeral namespace then proved Lunar Tear Internet access while its initiation toward a YoRHa listener was blocked. Removed Lunar Tear from this Mac's remembered networks after testing so it does not auto-join.
- OpenTofu reports **No changes** after creating Lunar Tear. No passphrase, ONT identity, WAN MAC, public address, or unredacted diagnostic entered Git.

Direct service passed its selected speed and reboot gates without the BGW620. The ten-minute stability hold remains explicitly waived rather than passed.
