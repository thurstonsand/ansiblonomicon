# New-house Internet cutover

## Destination

A factory-fresh UDMP provides the new house's Internet directly through the WAS-110, with separate Bunker, YoRHa, and Lunar Tear networks, one newly adopted AP and real household SSIDs, and a reboot-tested wired path that no longer depends on the BGW620.

## Notes

- Execution is in scope. The map closes only after the physical cutover and verification complete.
- Existing research lives in the Bunker Rebuild's [Fiber bypass device stability](../bunker-rebuild/tickets/16-fiber-bypass-stability.md), [VLAN security redesign](../bunker-rebuild/tickets/13-vlan-security-redesign.md), and [UDMP declarative rebuild](../bunker-rebuild/tickets/15-udmp-declarative-rebuild.md).
- Reset the UDMP while the BGW620 remains the known-good WAN, then reprofile and cut over the WAS-110. Do not prove the bypass against controller state that will immediately be erased.
- Leave all APs disconnected until the UDMP reset completes. Factory-reset and adopt one AP afterward, so no device can rejoin an old SSID.
- Bootstrap UniFi with its owner account and a Local Access Only recovery administrator.
- Keep gateway, WAN, and ONT identity values out of committed files. The BGW620 remains immediately reconnectable only until direct service passes its speed and reboot tests.
- The user chose the local Pi transcript, rather than a separate offline runbook, as the unavailable-Internet guide.
- Use `agent-browser` for the BGW620 and UniFi dashboards. Do not ask the user to transcribe facts those dashboards expose.

## Decisions so far

- [BGW620 and WAS-110 service profile](tickets/01-bgw620-was110-profile.md): use the new gateway's ONT identity on the stick and its distinct WAN MAC on the UDMP; force 10 Gb/s, preserve the management route, and require O5.1 plus valid extended VLAN tables before judging DHCP.
- [Bunker and YoRHa bootstrap design](tickets/02-infra-admin-bootstrap-design.md): create untagged Bunker at `10.10.10.0/24` and YoRHa VLAN 20 at `10.10.20.0/24`, using the zone matrix for one-way YoRHa authority and WPA3-only Wi-Fi.
- [Cutover sequence and safety gates](tickets/03-cutover-safety-gates.md): move the BGW620 to `192.168.10.0/24`, prove the entire clean UniFi slice behind it, then validate the WAS-110 layer by layer with fixed timeouts and fiber-back rollback before isolated speed and reboot acceptance tests.
- [UDMP bootstrap execution](tickets/04-factory-reset-and-bootstrap-udmp.md): use OpenTofu 1.12 with `ubiquiti-community/unifi` 0.55.0 and R2 state for stable controller resources after manual bootstrap and zero-change imports; keep credentials, adoption, WAN identity, physical WAN bindings, and unproven routing APIs manual and documented.
- [WAS-110 cutover execution](tickets/05-reprofile-was110-and-cut-over.md): the BGW620 profile reached O5.1 with valid extended VLAN tables and healthy optics; a static interface route, rather than a policy-based route or private alias, preserves LCT access through WAN2.
- [Direct-service verification](tickets/06-verify-direct-service.md): direct wired service and both gateway speed tests exceeded 5 Gbps, and the one permitted UDMP reboot restored the public lease, O5.1, LCT, DNS, and Internet without repair. The user waived the interrupted ten-minute stability hold.
- Lunar Tear is VLAN 30 at `10.10.30.0/24` with its own zone and a WPA2/WPA3 transition WLAN on 2.4 and 5 GHz. Representative testing proved Internet access and blocked initiation toward YoRHa.

## Not yet specified

## Out of scope

- The remaining Scanners, The Village, and Transporter networks; their firewall matrix, mDNS policy, and device migrations belong to the subsequent whole-house network effort.
- Adoption and RF tuning of the remaining APs belongs to Bunker Rebuild's [WiFi coverage survey and RF tuning at the new house](../bunker-rebuild/tickets/21-wifi-coverage-and-tuning.md).
- Full OpenTofu ownership of the UniFi controller, NextDNS reconstruction, and blank-router Ansible completeness remain later declarative-rebuild work.
- IPv6 restoration, a 24-hour thermal observation, and a one-week BGW620 rollback window are not completion gates for this cutover.
