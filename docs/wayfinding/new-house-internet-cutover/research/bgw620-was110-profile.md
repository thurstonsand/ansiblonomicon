# BGW620-700 WAS-110 service profile

## Scope and verdict

This is the direct XGS-PON profile for the supplied BGW620-700 and the existing WAS-110 running 8311 Community Firmware basic v2.8.3. The prior stability research is still useful for observability and recovery, but it predates this gateway profile and does not establish it. The PON.wiki BGW620 guide is the primary authority for the ONT emulation. Ubiquiti documents the UDM Pro with a default 10G SFP+ WAN port and two 10G/1G SFP+ ports, so the stick belongs in that designated SFP+ WAN port. [PON.wiki BGW620 guide](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw620-700-with-the-was-110/) [Ubiquiti UDM Pro specifications](https://techspecs.ui.com/unifi/cloud-gateways/udm-pro?subcategory=all-cloud-gateways)

The existing gateway's observed XGS-PON evidence is sufficient to use this path. PON.wiki identifies 1270 nm upstream as XGS-PON, while its guide warns that some 6x firmware reports zero instead. Do not move an identity from another address or another gateway. Capture the identity of the supplied, provisioned BGW620-700 at this address and retain the gateway as rollback until AT&T has completed provisioning and closed the installation ticket. [PON.wiki BGW620 guide, XGS-PON verification and new-installation warning](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw620-700-with-the-was-110/#verify-xgs-pon-service)

## Two identities, two devices

These are separate values with different jobs. Mixing them produces a particularly unhelpful outage.

| Belongs on | Value | Source and use | Repository rule |
| --- | --- | --- | --- |
| WAS-110 PON profile | The **PON Serial Number, ONT ID** from the BGW620-700 bottom label | Identifies the emulated ONT to the OLT. This is the value the documented profile says to replace with the supplied gateway's label value. | Secret. Store only in the approved secret store or an offline cutover worksheet. |
| WAS-110 PON profile | Equipment ID `iONT620700X`; Hardware Version `BGW620-700_2.5`; Sync Circuit Pack Version enabled; MIB File `/etc/mibs/prx300_1U.ini`; **Fix VLANs** enabled | Exact current PON.wiki BGW620-700 profile values. | The constants are not credentials, but do not put a live profile export in the repository. |
| WAS-110 PON profile | Software Version A and B `BGW620_<Current software version>` | On the BGW620 update page, copy the supplied gateway's **Current software version** into PON.wiki's generator. It prefixes `BGW620_`; apply the resulting value to both fields. | Do not record the gateway's observed firmware release in this document or commit it with an identity export. |
| UDMP Internet WAN | The BGW620-700's **WAN MAC address** | Clone this onto the physical SFP+ WAN interface that carries the WAS-110. AT&T DHCP keys the lease to this MAC, not to the stick's PON serial. | Secret and live service identifier. Do not add it to UniFi exports, Ansible, notes, screenshots, or commits. |

PON.wiki instructs the operator to take the ONT serial from the label and gives the remaining PON-tab values above. It separately requires cloning the BGW620 MAC to the router's DHCP WAN physical interface, because AT&T can retain the prior lease for roughly 30 minutes. The WAS-110 is an SFU ONT, not a router. It does not perform the UDMP's DHCP client, NAT, or MAC cloning. [PON.wiki BGW620 profile configuration](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw620-700-with-the-was-110/#configure-ont-settings) [PON.wiki BGW620 pre-configuration and router tips](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw620-700-with-the-was-110/#pre-configuration)

PON.wiki's static configuration example still prints `BGW620_5.31.9`, but its current Software Versions section directs the operator to copy the source gateway's **Current software version** from the BGW620 update page into a form that generates the `BGW620_<version>` attribute. For a gateway newer than the example, use that source-provided generated value in both fields. This resolves the stale example without copying an old-house profile or inventing a version string. Recheck the linked PON.wiki profile immediately before write access in case it has changed.

## Configure the WAS-110

The existing stick is already on supported 8311 Community Firmware v2.8.3, so use its 8311 LuCI configuration page rather than an Azores firmware flow:

1. Reach `https://192.168.11.1/cgi-bin/luci/admin/8311/config` as `root`.
2. On **PON**, enter the source gateway ONT ID and the exact non-secret BGW620 profile values in the table above.
3. On **ISP Fixes**, enable **Fix VLANs**.
4. On **Device**, set **Ethtool Speed Settings** to `10000`.
5. Save and reboot the stick. The 8311 guide explains that configuration lives in duplicated U-Boot environments. Its shell helper writes both; do not use a one-bank hand edit.

PON.wiki specifies the PON and ISP-Fixes steps for the BGW620 profile. Its troubleshooting guide says the WAS-110 often autonegotiates down to 1 Gb/s and calls for forcing both host and stick to 10 Gb/s. The stick-side persistent setting is `10000`; set the matching UDMP SFP+ port to 10 Gb/s, not Auto or 1 Gb/s, then verify the negotiated link after installation. [PON.wiki BGW620 configuration](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw620-700-with-the-was-110/#configure-ont-settings) [PON.wiki link-speed troubleshooting](https://pon.wiki/guides/troubleshoot-connectivity-issues-with-the-was-110-or-x-onu-sfpp/#link-speed) [8311 firmware A/B architecture](https://pon.wiki/guides/install-the-8311-community-firmware-on-the-was-110/#a-b-architecture)

The `fwenv_set` shell alternative is useful only when the LuCI path is unavailable. It requires the real ONT ID as an argument, so it is deliberately not reproduced with a command line here. Do not factory-reset the WAS-110. It would erase its 8311 U-Boot configuration, while the required service values exist only in the secret capture.

## UDMP WAN and LCT management

Configure the UDMP's SFP+ port as the DHCP Internet WAN carrying the WAS-110, clone the BGW620 WAN MAC on **that physical WAN interface**, and force its link speed to 10 Gb/s. A fresh UDMP must complete its initial setup through the working BGW620 first. Do not mistake that temporary Ethernet WAN for the direct-PON WAN or clone the MAC onto a LAN port.

The stick's Local Craft Terminal is `192.168.11.1/24` on the WAN side. Keep `192.168.11.0/24` distinct from every UDMP LAN, including Bunker and YoRHa. In UniFi Network 9.4 or later, create an interface route after assigning the SFP+ port to WAN:

| Field | Value |
| --- | --- |
| Name | `WAS-110` |
| Device | Gateway |
| Type | Interface |
| Value | The SFP+ WAN carrying the stick |
| Destination | `192.168.11.0/24` |

The current PON.wiki UniFi OS instructions place this at **Settings > Policy Table > Create New Policy > Route**. On Network 9.3 it is **Settings > Policy Engine > Policy-Based Routes > Create Route**, and on 9.2 or earlier it is **Settings > Routing > Static Routes**. Ubiquiti's current policy-route documentation confirms that a route can target a specific WAN interface. Select the actual SFP WAN interface if the UI names it WAN2 or otherwise differs from the guide's generic `WAN`. [PON.wiki Accessing the ONT, UniFi OS](https://pon.wiki/guides/accessing-the-ont/#static-route-restricted-environments) [Ubiquiti policy-based routing](https://help.ui.com/hc/en-us/articles/12566175125783-UniFi-Gateway-Policy-Based-Routing)

A mere route is sufficient here because 8311's reverse-ARP daemon learns the incoming management client and supplies the otherwise asymmetric return path. This is a 8311 firmware feature, not a generic ONT behavior. If access fails while the fiber is attached, physically disconnect the fiber before diagnosis: the OLT can disable the LCT administrative state. A local management host can instead use `192.168.11.2/24` directly on the attached interface for recovery, but must restore its normal addressing afterward. [PON.wiki Accessing the ONT](https://pon.wiki/guides/accessing-the-ont/)

## Safe cutover order and gates

1. **Keep the BGW620 service intact.** Record the source gateway's ONT ID and WAN MAC privately, confirm the supplied gateway still passes service, and leave its fiber and Ethernet path ready as rollback. No live identifier enters this repository.
2. **Bootstrap the factory-reset UDMP behind the working BGW620.** Connect the laptop by Ethernet directly to the UDMP, finish the owner/cloud and Local Access Only recovery-admin setup, and create only Bunker and YoRHa. Keep APs disconnected until the old controller state is erased, as already decided. Prove ordinary Internet service through the BGW620 before touching PON equipment.
3. **Prepare direct-WAN policy before moving fiber.** Assign the designated SFP+ port as the direct Internet WAN, configure DHCP, the 10 Gb/s host speed, the BGW620 WAN-MAC clone, and the `192.168.11.0/24` interface route. Verify that no UDMP LAN overlaps the stick management subnet. The direct WAN may temporarily be a second WAN while the BGW620 path remains the primary recovery path. Do not assume the UI's WAN label names a physical port.
4. **Profile the stick with the fiber disconnected if necessary.** Install it in the prepared UDMP SFP+ WAN port, reach its LCT through the management route, apply the BGW620 PON profile and `Fix VLANs`, force the stick to 10 Gb/s, save, and reboot. Do not expose an optical connector to the eye. PON.wiki directs operators to reboot before moving the SC/APC fiber and to confirm its connection.
5. **Move fiber once and validate the ONT before judging DHCP.** Wait for the stick to show in-spec optical RX/TX and **O5.1, Associated**. Then inspect **VLAN Tables** at `https://192.168.11.1/cgi-bin/luci/admin/8311/vlans`. “No Extended VLAN Tables Detected”, an empty table, or only deceptive default rules means O5 alone did not complete the usable OMCI configuration. Stop and restore the BGW620. Do not change the MAC clone to cure this.
6. **Validate routing and service.** Confirm a 10 Gb/s host link, LCT reachability through the UDMP route, and a UDMP DHCP lease on the cloned-MAC SFP+ WAN. Then test external connectivity, expected speed, and a controlled UDMP reboot. O5.1 plus valid extended VLAN state plus a healthy host link isolates a remaining failure to the UDMP DHCP/WAN configuration rather than the PON profile.
7. **Rollback instead of experimenting.** If a gate fails, move the fiber back to the BGW620 and restore its known-good Ethernet WAN path to the UDMP. Keep the failure state and any redacted observations. Do not repeatedly reprogram the ONT identity or power-cycle away evidence. Retain the BGW620 until the direct path passes the speed and UDMP-reboot gates.

PON.wiki defines O5 as the operation state, but explains that “fake O5” is successful PLOAM activation followed by failed OMCI configuration. Its direct discriminator is the extended VLAN table: blank output fails, and default-only output can mislead. The BGW620 guide repeats this check specifically for its profile. [PON.wiki PLOAM and OMCI troubleshooting](https://pon.wiki/guides/troubleshoot-connectivity-issues-with-the-was-110-or-x-onu-sfpp/#olt-authentication) [PON.wiki BGW620 validation](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw620-700-with-the-was-110/#validate-olt-authentication)

## Keep out of Git

Never commit or paste into an issue, screenshot, UniFi export, shell history intended for sharing, or this research document:

- BGW620 ONT ID, serial, PON serial, registration values, label photos, or fiber-stat identifiers.
- BGW620 WAN MAC, the cloned UDMP WAN MAC, public lease address, DHCP lease details, or any other live MAC address.
- Gateway access code, UDMP Local Access Only credentials, owner/cloud account tokens, stick credentials, private backups, or exports containing any of them.
- Raw diagnostic logs unless identifiers, addresses, and credentials have been redacted first.

The documented profile constants above are enough to prepare the procedure. The two per-service identity values stay in the approved secret store and are entered interactively at cutover.

## Sources

- [PON.wiki, Masquerade as the AT&T Inc. BGW620-700 with the WAS-110 or HLX-SFPX](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw620-700-with-the-was-110/)
- [PON.wiki, Accessing the ONT](https://pon.wiki/guides/accessing-the-ont/)
- [PON.wiki, Troubleshoot connectivity issues with the WAS-110 or X-ONU-SFPP](https://pon.wiki/guides/troubleshoot-connectivity-issues-with-the-was-110-or-x-onu-sfpp/)
- [PON.wiki, Install the 8311 community firmware on the WAS-110](https://pon.wiki/guides/install-the-8311-community-firmware-on-the-was-110/)
- [Ubiquiti, Dream Machine Pro technical specifications](https://techspecs.ui.com/unifi/cloud-gateways/udm-pro?subcategory=all-cloud-gateways)
- [Ubiquiti, UniFi Gateway policy-based routing](https://help.ui.com/hc/en-us/articles/12566175125783-UniFi-Gateway-Policy-Based-Routing)
