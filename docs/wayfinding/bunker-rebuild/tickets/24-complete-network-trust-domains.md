---
status: closed
type: task
blocked-by: []
claimed: 01a05cfb-8dd1-7255-9615-e02b82b6956c
---

# Complete the network trust domains

## Question

Extend the clean new-house controller from Bunker, YoRHa, and Lunar Tear to the six-domain model settled by [VLAN security redesign](13-vlan-security-redesign.md). Establish the empty destination networks and policies before importing client state, so every retained device has a valid home rather than being recreated in whichever network happens to exist.

## Work

- Add Scanners as VLAN 40 at `10.10.40.1/24`, with DHCP `.100` through `.249`, IPv6 disabled, and its own firewall zone.
- Add The Village as VLAN 50 at `10.10.50.1/24`, with DHCP `.100` through `.249`, IPv6 disabled, and its own firewall zone.
- Preserve Transporter as the zone for restored WireGuard Server and Identity VPN client networks rather than inventing a VLAN 60. Retain the prior server ranges only after the encrypted backup and live controller establish their exact identities.
- Add the minimum named exceptions over the zone matrix: YoRHa may initiate toward Lunar Tear, Scanners, and The Village; Lunar Tear may initiate toward Scanners. Bunker, Scanners, and The Village do not initiate toward client or infrastructure zones. All LAN zones retain Gateway and External access through the controller defaults.
- Create reusable Scanners and The Village access profiles. Infrastructure trunks continue allowing all VLANs.
- Decide WLAN security from the retained-device inventory before broadcasting either SSID. Do not reuse an old SSID merely to cause an uncontrolled mass migration.
- Keep scoped mDNS disabled until the client inventory identifies the services and migration testing can prove the intended YoRHa/Lunar Tear to Scanners behavior.

## Completion

OpenTofu owns both new networks, zones, policies, and access profiles with a full **No changes** plan. Representative packet tests prove the new intended allow paths and default-denied initiation without exhaustively retesting the established matrix. Transporter is either restored with verified source material or left as an explicitly blocked follow-up for the migration ticket.

## Execution record

- Created Scanners as VLAN 40 at `10.10.40.1/24` and The Village as VLAN 50 at `10.10.50.1/24`, each with DHCP `.100` through `.249`, fixed `/24` scaling, and IPv6 disabled.
- Created matching firewall zones and reusable single-network access profiles. Existing infrastructure trunks carry both VLANs automatically.
- Added named stateful allows from YoRHa to Lunar Tear, Scanners, and The Village, plus Lunar Tear to Scanners. The zone matrix remains the default denial for every unapproved inter-zone initiation.
- Kept both new WLANs dark so old clients cannot migrate before review.
- Proved YoRHa to The Village and Lunar Tear to Scanners initiation, The Village Internet access, and blocked The Village to YoRHa initiation through ephemeral clients attached to the real bridges. Removed all test interfaces and listeners afterward.
- Transporter remains a VPN zone rather than VLAN 60. Its WireGuard and Identity VPN networks wait for verified preserved material in [Migrate approved clients and scoped discovery](26-migrate-clients-and-discovery.md).
- OpenTofu applied ten additions with no changes or destroys and then converged to **No changes**.
