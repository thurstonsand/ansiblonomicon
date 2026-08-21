# Fiber bypass stability

## Verdict

The leading hypothesis is **thermal instability in the WAS-110**, not an AT&T authentication renewal. Read-only inspection found the stick's two CPU thermal zones at **82.4°C** and **79.7°C** after five days of uptime. That is far beyond the 8311 community's “provide sufficient cooling” threshold of 60°C, although it does not prove the temperature at the prior outages caused the lockup. The optical path is currently healthy: O5.1 associated, no active PON alarms, Tx 5.59 dBm, and Rx -17.99 dBm.

The recovery ritual also leaves a serious second candidate: an SFP host/link wedge. A stick power cycle resets the PON SoC and its 10G host PHY; rebooting the UDMP resets the other end. A DHCP failure should recover from a UDMP WAN/DHCP reset while the stick remains registered, so its needing both resets is a poor fit. There is no source-backed basis for a recurring AT&T residential XGS-PON client certificate renewal failure here. The direct-bypass flow authenticates the emulated ONT to the OLT with the AT&T gateway's ONT identity and then gets WAN DHCP using the gateway WAN MAC.

Root-cause confirmation remains open until a failure is captured before either device is reset.

## Read-only live baseline — 2026-08-19

This was an SSH-only inspection of the production stick. No configuration, firmware, or host state was changed. Identifiers and MAC addresses are deliberately omitted.

| Observation | Result | Meaning |
| --- | --- | --- |
| Firmware | 8311 Community Firmware **basic v2.8.0** (`f4e4db3`), active bank B; released 2024-12-01 | It is two releases behind current v2.8.3. It lacks the v2.8.2 metrics endpoint. |
| Uptime / last reset marker | 5d 13h; boot environment says `POR_RESET` | Consistent with the reported physical power cycle. RAM-backed `logread` contains only this boot, so it cannot explain the previous outage. |
| SoC temperatures | 82.4°C and 79.7°C | Strong reason to correct cooling before the move. These are CPU-zone readings, not the optical DDM temperature. |
| Optics | 74°C; Tx 5.59 dBm; Rx -17.99 dBm; 3.25 V; no active alarms | Both optical power readings are in PON.wiki's good ranges. No present LOS/LODS or rogue-ONT evidence. |
| PON state | O5.1, Associated; authentication status 0 | The OLT presently accepts the emulated ONT. A registration/authentication fault is not active now. |
| Stick-to-UDMP Ethernet | 10,000 Mb/s, full duplex, link detected | The link is healthy now. The stick is not configured with an explicit persistent `8311_ethtool_speed`, so record the UDMP port setting before changing anything. |
| Relevant 8311 services | RX_LOS daemon is deliberately deasserting Rx LOS; the ping daemon is running | The ping daemon only sends a management-plane ping every five seconds. It is not a WAN-recovery watchdog. Do not disable the hardware watchdog or blame this daemon without failure evidence. |

The community documentation advises active cooling and says that temperatures over 60°C are within specification but can reduce product life. The guide exposes separate CPU and optic temperature metrics in v2.8.2+, which makes temperature trend capture practical after updating. [WAS-110: Active Cooling](https://pon.wiki/xgs-pon/ont/bfw-solutions/was-110/)

## Failure modes and discriminators

| Failure mode | Fit to weekly outage + both resets | What it looks like before recovery | What rules it in or out |
| --- | --- | --- | --- |
| **SoC/optics thermal lockup** | **Best current fit.** Heat accumulates in a high-power SFP+ cage over days; power removal is a credible way to clear a wedged module. The live CPU readings make this actionable even before proof. | Stick management may time out or stall; PON status may be unavailable, frozen, or show alarms. The UDMP's physical SFP link can remain up while traffic is dead. | Capture CPU/optic temperatures and stick logs immediately. Test after sustained active cooling. A materially cooler stick that stops failing is strong evidence. |
| **UDMP ↔ stick host-link/SFP cage wedge** | Plausible. The required two resets can simply reset both sides of the 10G link. | `ethtool` on the UDMP WAN device shows no link, unexpected 1G, module read failure, or link transitions. Stick `eth0_0` is down or no longer 10G. PON can remain O5.1. | Preserve `ethtool`/kernel logs on both sides. 8311 documents that host autonegotiation often falls back to 1G and recommends forcing 10G. The current link is 10G, but that is not evidence about the failure. [Troubleshoot: Link Speed](https://pon.wiki/guides/troubleshoot-connectivity-issues-with-the-was-110-or-x-onu-sfpp/#link-speed) |
| **PON loss / registration drop** | Possible, but a UDMP reboot is not inherently required. | PLOAM is O1–O4 rather than O5.1, or active LOS/LODS alarms appear. Optical power can be out of range. O7 is an emergency/rogue state: disconnect the fiber and get community/ISP help rather than repeatedly reconnecting it. | `pontop -b -g s`, `pontop -b -g w`, and optical status distinguish this cleanly. O5.1 with no usable service instead calls for the OMCI/VLAN and WAN checks below. [Troubleshoot: PLOAM and alarms](https://pon.wiki/guides/troubleshoot-connectivity-issues-with-the-was-110-or-x-onu-sfpp/#olt-authentication) |
| **OMCI/VLAN “fake O5”** | Lower fit for a stable service that fails weekly, but check it after a PON event or configuration change. | It reports O5.1 but the OLT has not supplied usable extended VLAN tables, so traffic never reaches WAN. | Dump the extended VLAN tables. A blank/no meaningful table is the discriminator. [Troubleshoot: OMCI clarification](https://pon.wiki/guides/troubleshoot-connectivity-issues-with-the-was-110-or-x-onu-sfpp/#omci-clarification) |
| **AT&T DHCP/MAC lease** | Lower fit. A DHCP issue should leave PON and 10G link healthy and should respond to restarting only the UDMP WAN client. | Stick remains O5.1 and passing link, while the UDMP has no IPv4 lease or renewal/NAK errors. | Capture UDMP lease/DHCP logs and WAN address before reboot. AT&T's documented bypass guidance ties the lease to the gateway WAN MAC and describes a roughly 20–30 minute window when hardware is swapped without MAC cloning; it does **not** document a weekly renewal bug. [AT&T BGW320 guide: DHCP MAC spoofing](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw320-500-505-with-the-was-110/#dhcp-mac-spoofing) |
| **802.1X/certificate renewal** | Unsupported hypothesis. | Would need an explicit EAP/certificate failure in logs, which this direct XGS-PON architecture has not supplied. | Do not change certificates speculatively. The 8311 project mentions 802.1X as one of many interoperability concerns, but the AT&T XGS-PON procedure uses the gateway ONT identity, PLOAM/OMCI, VLAN handling, and DHCP MAC cloning—not a documented periodic certificate renewal. [8311 installation rationale](https://pon.wiki/guides/install-the-8311-community-firmware-on-the-was-110/) |

I found no primary Ubiquiti or 8311 source substantiating a UDMP-specific “Marvell switch chip” defect that causes these periodic failures. Treat that claim as an unverified operator theory, not a mitigation target. The generic 8311 host-link behavior is documented and is enough to instrument.

## Capture this before any reboot

Record the wall-clock time and do **not** reboot, reseat, or pull fiber until both snapshots below are saved. Run the stick commands from a machine that can already reach its management address; save outputs locally and redact ONT serials, MAC addresses, and public addresses before sharing them.

### Stick — SSH as `root` to `192.168.11.1`

Run this once now as a baseline and again during the outage. All commands below are read-only.

```sh
ssh root@192.168.11.1 '
  date; uptime
  cat /etc/8311_version
  . /lib/8311.sh; active_fwbank; inactive_fwbank
  pontop -b -g s
  pontop -b -g "Optical Interface Status"
  pontop -b -g w
  pontop -b -g "GEM/XGEM Port Counters"
  ethtool eth0_0
  for zone in /sys/class/thermal/thermal_zone*; do
    printf "%s " "$zone"; cat "$zone/type" "$zone/temp"
  done
  dmesg
  logread
' | tee "was-110-$(date +%Y%m%d-%H%M%S).log"
```

Then, while it is still O5.1 but traffic is unavailable, collect the OMCI discriminator:

```sh
ssh root@192.168.11.1 '
  8311 -extvlan-decode.sh -t
  omci_pipe.sh md | grep -E "^\|\s+(84|171)\s\|"
  omci_pipe.sh meg 131 0
'
```

Interpret the capture as follows:

- **No SSH/LCT response**, high temperature just before loss, or a frozen `pontop`: thermal/SoC wedge moves to the front.
- **PLOAM other than O5.1** or LOS/LODS alarms: retain the optical readings and involve AT&T if the physical signal is bad.
- **O5.1 plus no extended VLAN entries**: fake O5/OMCI configuration. Do not randomly alter the emulated gateway identity.
- **O5.1, valid VLAN table, 10G stick link**, but UDMP has no lease: inspect UDMP DHCP, MAC clone, and host link next.

`pontop` is the documented shell interface for PLOAM state, optics, and alarms. The guide's published optical ranges rate the current Tx 5.59 dBm and Rx -17.99 dBm as good. [WAS-110 troubleshooting](https://pon.wiki/guides/troubleshoot-connectivity-issues-with-the-was-110-or-x-onu-sfpp/)

### UDMP — WAN snapshot

First identify the physical SFP+ WAN interface rather than assuming an interface number; UniFi OS releases and port assignments differ. In the UDMP SSH shell, run `ip -br link` and correlate the interface with the SFP+ WAN port in Port Manager. Replace `WAN_IF` below with that physical interface.

```sh
ip -br link
ip -br addr
ip route
ethtool WAN_IF
ethtool -m WAN_IF
ip -s link show dev WAN_IF
journalctl -k -b --no-pager | grep -Ei 'WAN_IF|sfp|link|dhcp|udhcpc|udapi'
journalctl -b --no-pager | grep -Ei 'WAN_IF|sfp|link|dhcp|udhcpc|udapi'
```

Also save a screenshot/export of the UniFi Internet/WAN event timeline showing link state, DHCP address, and outage time. At the failure, record whether:

1. `ethtool WAN_IF` reports 10G/full/link detected versus link down or an unexpected speed;
2. `ethtool -m WAN_IF` can still read the module's DDM temperature/power data;
3. the UDMP still has an IPv4 WAN address and default route; and
4. the failure clears after **only** a UDMP reboot, **only** a stick power cycle, or requires both. Test one recovery at a time only after the snapshots are safe; it is the highest-value discriminator.

The 8311 documentation explicitly lists `ethtool -m <interface>` as a UniFi OS/Linux way to obtain the module DDM readings. [WAS-110 monitoring](https://pon.wiki/xgs-pon/ont/bfw-solutions/was-110/#temperature-monitoring)

## Ranked stabilization plan

1. **Cool the installed stick first.** Add a small heatsink only if it physically fits without stressing the cage, and provide continuous forced airflow across the UDMP SFP+ area with a quiet fan. Keep the rack/cage unobstructed. Trend both SoC zones and optic temperature for a week before and after. The live 82°C SoC reading makes this the only mitigation justified immediately; do not wait for the move.

2. **Update deliberately from v2.8.0 to the current official 8311 community basic release, v2.8.3.** Do this in a scheduled maintenance window after capturing the current configuration and confirming both A/B-bank recovery options. Use the project's `local-upgrade.tar` supplementary-upgrade path, not the older Azores web upgrader. The official guide calls the supplementary upgrade safe; it warns that the Azores web upgrade can soft-brick. [8311 upgrade guide](https://pon.wiki/guides/install-the-8311-community-firmware-on-the-was-110/#supplementary-upgrades)

   This is an observability and maintenance update, not a claimed thermal cure. v2.8.0 already contains the relevant older binary crash fixes for some VoIP MIBs. v2.8.2 adds the unauthenticated JSON metrics endpoint and an additional MIB; v2.8.3 only fixes displaying that MIB. There is no release note claiming either fixes a weekly heat/host-link hang. [v2.8.0](https://github.com/djGrrr/8311-was-110-firmware-builder/releases/tag/v2.8.0), [v2.8.2](https://github.com/djGrrr/8311-was-110-firmware-builder/releases/tag/v2.8.2), [v2.8.3](https://github.com/djGrrr/8311-was-110-firmware-builder/releases/tag/v2.8.3)

3. **Preserve a fixed 10G host link, but change it only with evidence.** The stick currently reports a good fixed 10G link. Confirm the UDMP SFP+ WAN port is likewise fixed to 10G and does not renegotiate to 1G during an outage. If it does, use the 8311 Device-tab persistent `Ethtool Speed Settings = 10000` and the corresponding UDMP 10G port setting in the same maintenance window. 8311 warns that autonegotiation often falls back to 1G. Do not toggle the RX_LOS or ping-daemon settings as a cure: RX_LOS is already being deasserted, and the ping daemon merely keeps the management route alive.

4. **Install an independent recovery watchdog at the new house.** A normal cloud/Wi-Fi smart plug is unsuitable: when it turns off the UDMP it often loses the control path needed to turn it back on, and it does not separately power an SFP stick inside the UDMP cage. The simple reliable design is a small wired, static-IP watchdog/relay powered independently of the UDMP. It probes at least two public IPs through the UDMP; after a sustained failure (for example, five minutes), it cuts **the UDMP AC input** for 15–30 seconds, then rate-limits itself to one recovery per hour and records the event locally. That one power cut also removes power from the stick, matching the proven manual ritual. It should not depend on Home Assistant, UniFi cloud, or an Internet API.

   Deploy this only after cooling and fault capture: automatic recovery must not erase the evidence needed to confirm the real failure. It is resilience, not remediation.

5. **Escalate or replace only based on captured signature.** Persistent bad Rx/LOS after cooling is AT&T/physical plant work. O5 failure with normal optics is an ONT identity/OMCI issue for the 8311 community. Repeated 10G host-link failure with healthy PON is a UDMP cage/host compatibility issue; try the other SFP+ cage as a controlled test before adding an intermediary switch. Do not add an external media converter merely to make a smart plug possible—it adds another power and link failure domain.

## Move day requirements — AT&T Fiber

The stick carries an emulation of the **old address's AT&T gateway/ONT identity**. Do not assume that identity is valid at a new service address/PON. AT&T must install and provision the new service using the gateway it supplies for that address. The 8311 AT&T guides explicitly say to keep that gateway in active service for roughly one to two weeks, until provisioning and the installation ticket are closed. [BGW320 guide](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw320-500-505-with-the-was-110/), [BGW620 guide](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw620-700-with-the-was-110/)

1. Before ordering hardware changes, verify the new service is **XGS-PON**. A WAS-110 is wavelength-specific; the AT&T guide identifies XGS-PON by 1270 nm upstream / the red-or-orange transceiver latch. A new address may be provisioned differently.
2. Let the installer complete the new AT&T gateway/ONT activation. Keep that gateway and its fiber connected until service is solid and the ticket is closed. Do not tell AT&T to register the bypass stick or expect to move the old gateway unchanged; follow AT&T's service-transfer process. [AT&T move process](https://www.att.com/help/moving/)
3. Capture the **new** supplied gateway's ONT ID/serial, model, hardware version, current software version, and WAN MAC from its label/fiber-status page. Store the values securely. They are service identity, not generic WAS-110 settings.
4. Reconfigure the stick in a maintenance window to emulate that new gateway model and ONT ID, then verify O5.1 plus extended VLAN tables. The 8311 guides give separate identity values for BGW320-500, BGW320-505, and BGW620-700; use the guide matching the new gateway rather than copying the old profile. [BGW620 configuration](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw620-700-with-the-was-110/#configure-ont-settings)
5. Clone the **new gateway WAN MAC** onto the UDMP WAN interface before switching. This avoids AT&T DHCP's old-lease wait when hardware changes. Confirm the UDMP uses DHCP WAN and retain the LCT management route.
6. Re-run the baseline capture, confirm 10G/full link, O5.1, optical power, stable DHCP, and temperature trend before declaring bypass service complete. Keep the AT&T gateway available as the rollback ONT while validating stability.

No evidence found supports transferring an AT&T “certificate” from the old address. The required move-day reprovisioning is the new gateway/ONT identity at the new OLT and the new gateway WAN MAC, with AT&T completing its normal install first.

## Primary sources

- [PON.wiki — WAS-110 hardware, cooling, DDM, and 8311 metrics](https://pon.wiki/xgs-pon/ont/bfw-solutions/was-110/)
- [PON.wiki — troubleshoot WAS-110/X-ONU-SFPP connectivity](https://pon.wiki/guides/troubleshoot-connectivity-issues-with-the-was-110-or-x-onu-sfpp/)
- [PON.wiki — AT&T BGW320-500/505 masquerade](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw320-500-505-with-the-was-110/)
- [PON.wiki — AT&T BGW620-700 masquerade](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw620-700-with-the-was-110/)
- [8311 community firmware builder and release history](https://github.com/djGrrr/8311-was-110-firmware-builder/releases)
- [AT&T — transfer or move service](https://www.att.com/help/moving/)
