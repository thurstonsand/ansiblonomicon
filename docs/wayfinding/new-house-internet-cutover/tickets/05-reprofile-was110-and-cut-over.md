---
status: closed
type: task
blocked-by: [1, 4]
claimed: 01a05cfb-8dd1-7255-9615-e02b82b6956c
---

# Reprofile the WAS-110 and cut over

## Question

Execute the direct-bypass stage using the researched BGW620 service profile: capture the required new-house identity values without committing them, configure the WAS-110 and UDMP WAN, preserve the `192.168.11.0/24` management route, disconnect the supplied gateway, and bring the stick to O5 with usable service. Follow the approved safety gates exactly and restore the BGW620 rather than improvising if a stop condition fires.

## Execution record

- Inserted the fiber-disconnected WAS-110 into UDMP port 10 and required 10 Gb/s full duplex while the BGW620 remained the active WAN on port 9.
- Created the manual WAN2 source, cloned the concealed BGW620 WAN MAC directly from 1Password, and kept WAN1 preferred until the no-fiber profile passed.
- Found that a policy-based route could not reach the unnumbered stick before optical DHCP. Assigned temporary `192.168.11.2/24` directly to the identified Linux interface `eth9`, which proved LCT from the UDMP and wired YoRHa without changing WAN1.
- Replaced the old BGW320 identity with the captured BGW620 ONT profile in LuCI. Boolean comparison verified the concealed ONT ID plus equipment `iONT620700X`, hardware `BGW620-700_2.5`, both captured software fields, circuit-pack sync, XGS-PON, `/etc/mibs/prx300_1U.ini`, Fix VLANs, and 10 Gb/s Ethernet without printing identity values.
- Rebooted the stick once with fiber absent. Firmware v2.8.3, an O1.1 off-sync no-fiber state, and `eth0_0` at 10 Gb/s full duplex passed. LuCI returned just after the nominal 15-minute monitor boundary, so the event was recorded as late recovery rather than hidden.
- Moved the fiber once. The WAS-110 reached O5.1 Associated with no LOS/LODS alarm, meaningful extended VLAN data, two ME 84 entries, one ME 171 entry, and no fake-O5 marker. Initial optics were Rx `-15.53 dBm` and Tx `5.77 dBm`, both inside the accepted operating ranges.
- Obtained a direct public IPv4 lease on `eth9` without recording it. Port 10 remained 10 Gb/s full duplex and wired IP, DNS, HTTPS, and LCT checks passed.
- Removed the temporary LCT address and caught that the policy route sent management traffic toward the ISP gateway. Replaced it with the static interface route `192.168.11.0/24` through WAN2 at metric 1; the kernel installed a directly scoped `eth9` route and LCT HTTPS passed without a private alias. The live legacy route imported into `unifi_static_route`, resolves its controller interface and gateway identities through managed resources rather than committed IDs, and produces a zero-change plan. Removed the obsolete policy-based route.
- Disconnected BGW Ethernet from port 9. The controller removed the dead BGW Internet source after reboot; port 9 retains only its empty WAN1 hardware role while WAS-110 on WAN2 is the sole live source.
- Corrected the post-cutover WAN order after the dashboard exposed that the controller still considered healthy WAN2 an active failover. WAN2 is now Primary and online; empty WAN1 is Backup and disconnected. Direct DNS-over-HTTPS, LCT access, and a zero-change OpenTofu plan passed afterward. The BGW620 label remains a physical rollback position, not simultaneous failover: with the single fiber installed in the WAS-110, the BGW620 has no independent upstream path.

The optical and host boundaries are direct, the persistent management route survives without an alias, and no BGW data path remains. Ticket 06 may run direct-only acceptance and recovery.
