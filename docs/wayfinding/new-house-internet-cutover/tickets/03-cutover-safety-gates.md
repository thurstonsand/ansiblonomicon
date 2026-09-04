---
status: closed
type: grilling
blocked-by: [1, 2]
claimed: 01a05cfb-8dd1-7255-9615-e02b82b6956c
---

# Cutover sequence and safety gates

## Question

What exact sequence, confirmation gates, timeouts, and rollback branches take the current topology to the destination without confusing a UDMP bootstrap failure with a PON failure?

Cover the transitions from AT&T Wi-Fi to a direct wired UDMP session; factory reset while port 9 uses the BGW620 LAN as known-good WAN; proving the clean UDMP through the BGW620; disconnecting the supplied gateway and reprofiling the WAS-110; switching the UDMP to its direct public lease; and restoring the BGW620 if any gate fails. The local Pi transcript is the offline guide, so every command, dashboard path, expected observation, and stop condition needed during Internet loss must appear in the resolution before execution begins.

## Resolution

### Safety invariants

- The single SC/APC fiber remains in the BGW620 until the clean UniFi estate passes every bootstrap gate.
- The old controller backup is reference and rollback material only. Never restore it onto the clean UDMP.
- No ONT identity, WAN MAC, device access code, credential, public address, raw backup, or unredacted diagnostic enters Git or chat.
- Keep all unselected APs physically disconnected. Reset and adopt only the U7 Pro Max in this cutover.
- A failed gate permits one evidence-backed retry only where this procedure names one. Otherwise restore the BGW620 rather than experimenting.
- Preserve the installed Early Access channel and firmware. Do not install optional updates. Accept only an update required by first-run setup or adoption, while the BGW620 still supplies service, then restart the affected device's ten-minute stability gate.
- The Power Distribution Pro continues powering the Pro Max 24 PoE and UDMP through controlled outlets 5 and 7 during its factory reset. Do not touch its circuit breaker. Verify both devices remain powered as soon as the reset starts and again after adoption.

### Physical port contract

The UDM Pro's official numbering is not symmetric:

| Port | Cutover use |
| --- | --- |
| UDMP 1 | Bunker access and physical recovery |
| UDMP 2 | YoRHa access and wired test client |
| UDMP 9 | Temporary RJ45 Internet from a BGW620 LAN port |
| UDMP 10 | SFP+ Internet containing the WAS-110, required to link at 10 Gb/s full duplex |
| UDMP 11 | SFP+ LAN to a Pro Max 24 PoE SFP+ port over the existing 10G DAC or fiber pair |

Choose the switch's permanent port numbers later when the house is wired. For this cutover, record which 2.5 GbE PoE port powers the U7 Pro Max and which 1 GbE access port manages the Power Distribution Pro. The switch uplink and AP port use native Bunker and allow every VLAN; the PDU port is a Bunker access port.

### Timeouts and stop conditions

| Layer | Wait before intervention | Success | Failure action |
| --- | --- | --- | --- |
| UDMP factory reset or reboot | 15 minutes | Setup or local login page responds | Record display/LED state. Permit one power cycle only if the unit is unresponsive; otherwise stop on BGW Wi-Fi. |
| Switch, PDU, or AP reset/adoption | 10 minutes each | Device reports Online, not Adopting, Updating, or Managed by Other | Check power and link once; repeat the physical reset once only if old ownership remains. Do not start PON work. |
| Required firmware update | Vendor progress plus 20 minutes | Device returns Online and stays there for 10 minutes | Stop on BGW service. Do not update another device. |
| WAS-110 configuration reboot | 15 minutes | LCT responds and the host link is 10G/full | Reseat the stick once with fiber still disconnected; stop if LCT or 10G does not recover. |
| PON activation | 15 minutes | O5.1 Associated, acceptable optics, no active LOS/LODS, and valid extended VLAN tables | Capture once and roll back. O7 is immediate fiber removal, not a 15-minute wait. |
| Direct DHCP after valid PON | 5 minutes | Port 10 receives a direct public IPv4 lease | Capture once, renew DHCP once, wait five more minutes, then roll back. |
| BGW rollback | 15 minutes after returning fiber | BGW fiber operational, port 9 healthy, and wired Internet restored | Join retained BGW Wi-Fi, inspect `http://192.168.10.254`, and stop bypass work until supplied-gateway service is restored. |
| Final UDMP reboot | 15 minutes | Port 10, O5.1, valid VLAN state, public DHCP, DNS, and Internet all recover without intervention | Capture once and roll back immediately. No second reboot. |

### Phase 0: preserve the old state and prepare the BGW620

1. **Reach the old UDMP as a separate LAN.** Disable the Mac's BGW Wi-Fi, cable the Mac directly to an old-UDMP LAN port, and confirm Ethernet owns `192.168.1.0/24`. The BGW and old UDMP currently use the same subnet on physically separate Ethernet domains; never leave both active on the Mac at once. The local transcript remains visible without Internet. After backup, unplug old-UDMP Ethernet before re-enabling BGW Wi-Fi.

2. **Download and encrypt backups before reset.** In the old local console, open **Settings > Control Plane > Backups**. Download a current System Config backup and Network-only `.unf` backup. In the `Ubiquiti Account` 1Password item, add section `pre-reset backup` with a generated concealed `archive password`. Stage the downloads outside the repository:

   ```sh
   staging_dir="$(mktemp -d /tmp/udmp-backups.XXXXXX)"
   archive="$HOME/Documents/Network Backups/udmp-pre-reset-$(date +%Y%m%d-%H%M%S).tar.enc"
   mkdir -p "$(dirname "$archive")"
   printf 'staging: %s\narchive: %s\n' "$staging_dir" "$archive"
   ```

   Move both browser downloads into `staging_dir`, verify they are nonempty, then encrypt them with AES-256 and a PBKDF2-derived key without exposing the 1Password value:

   ```sh
   find "$staging_dir" -type f -size +0 -exec stat -f '%N %z bytes' {} \;
   tar -C "$staging_dir" -cf - . \
     | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 600000 \
         -pass file:<(op read 'op://agent/Ubiquiti Account/pre-reset backup/archive password') \
         -out "$archive"
   openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 \
     -pass file:<(op read 'op://agent/Ubiquiti Account/pre-reset backup/archive password') \
     -in "$archive" \
     | tar -tf - >/dev/null
   stat -f '%N %z bytes' "$archive"
   rm -rf "$staging_dir"
   ```

   Stop before reset unless both source files were nonempty and the encrypted archive decrypts and lists successfully. Record the installed UniFi OS, Network, Pro Max 24 PoE, Power Distribution Pro, and U7 Pro Max versions from the console. Do not change their release channel or request updates.

3. **Update 1Password in its UI.** Reshape the `AT&T Router` item to hold `model`, `management URL`, concealed `device access code`, Wi-Fi name/password, and a `Service identity` section containing concealed `ONT ID`, concealed `WAN MAC`, `software version`, and `captured at`. `XGS PON` retains the WAS-110 login and gains a Related Item link to `AT&T Router`. `Ubiquiti Account` retains its cloud login, OTP, and encrypted-backup password; its old `local admin` and `ssh` values will be replaced after reset. Create a `YoRHa WiFi` wireless-router item for its WPA3 credential. Verify 1Password opens while the Mac has no Internet. The user copies identity values directly between the BGW label/dashboard, 1Password, and later device forms; the values never pass through the transcript.

4. **Record the supplied-gateway baseline.** On BGW Wi-Fi, open `http://192.168.1.254`, then **Diagnostics > Speed Test**. The user enters the physical Device Access Code directly. Record only downstream and upstream results. Also require **Broadband > Status** to show fiber operational and the current wired/fiber links at 10 Gb/s.

5. **Remove the bootstrap subnet collision.** Open **Home Network > Subnets & DHCP**, authenticate with the Device Access Code, change the BGW private IPv4 address to `192.168.10.254/24`, and set DHCP to `.64` through `.253`. Its disabled guest SSID reserves `192.168.2.0/24`, so that otherwise-obvious bootstrap subnet is unavailable. Save once. Renew the Mac's Wi-Fi lease, reopen `http://192.168.10.254`, and verify:

   ```sh
   route -n get default | grep -E 'gateway:|interface:'
   ping -c 3 192.168.10.254
   ```

   The factory-default UDMP may now use `192.168.1.1/24` without overlapping its port 9 WAN. Leave the BGW at `192.168.10.254` through rollback and storage.

### Phase 1: clean UDMP and minimum UniFi estate

1. **Isolate the controller reset.** Keep fiber in the BGW. Disconnect UDMP ports 10 and 11, every AP, and downstream management Ethernet. Connect a BGW LAN port to UDMP port 9 and the Mac to UDMP port 1. Keep the switch and UDMP powered through PDU outlets 5 and 7.

2. **Factory-reset the UDMP.** With power stable, hold Reset for 5 to 10 seconds until its display/LED shows restore has begun. Wait up to 15 minutes for `https://192.168.1.1` or the first-run setup page. Complete ownership with the existing UI cloud account. Select clean setup and never Restore. Let the first-run flow install an update only if it refuses to continue without one.

3. **Create recovery administration before changing WAN.** In the Network application, open **Admins** in the left navigation, choose **+**, create the Local Access Only recovery administrator, and leave Remote Management disabled for that account. In console **Settings > Control Plane > Console**, enable SSH and replace `Ubiquiti Account`'s `local admin` and `ssh` values in 1Password. Console SSH uses `root`.

4. **Replace the default LAN with Bunker.** In Network, open **Settings > Networks**, edit the factory network, and set:

   | Field | Value |
   | --- | --- |
   | Name | `Bunker` |
   | VLAN | None, native untagged |
   | Gateway/subnet | `10.10.10.1/24` |
   | DHCP | Server, `.100` through `.249` |
   | DNS | Automatic/upstream |
   | IPv6 | Disabled |

   Apply once. The Mac will lose its default lease; renew Ethernet DHCP and reopen the console at `https://10.10.10.1`.

5. **Create YoRHa.** At **Settings > Networks > Create New Virtual Network**, set name `YoRHa`, VLAN 20, gateway `10.10.20.1/24`, DHCP `.100` through `.249`, automatic DNS, and IPv6 disabled.

6. **Create the zone contract.** At Network 9.4 or later, use **Settings > Zones**; on Network 9.3 use **Settings > Policy Engine > Zones**. Create custom Bunker and YoRHa zones, assign each same-named network to its zone, and create:

   - `YoRHa to Bunker`: allow all, stateful.
   - `Bunker to YoRHa`: block all.
   - preserve the required default access from both zones to Gateway services and External Internet.

   Inspect the zone matrix in both directions. Return traffic for a connection initiated by YoRHa remains statefully allowed; no reverse allow rule is needed.

7. **Reserve recovery ports.** In **Devices > UDM Pro > Ports > Port Manager**, make port 1 a Bunker access port and port 2 a YoRHa access port. Move the Mac to port 2, renew DHCP, and require a `10.10.20.100` through `.249` lease, DNS resolution, and Internet through port 9.

8. **Prove local recovery rather than merely creating it.** While the Mac remains on wired YoRHa, disconnect only the BGW Ethernet cable from port 9. In a private browser session open `https://10.10.20.1` and sign in with the Local Access Only account. Reconnect port 9 and require Internet to recover within five minutes. Failure blocks all further work.

9. **Adopt one device at a time.** Connect UDMP port 11 to a Pro Max 24 PoE SFP+ port at 10 Gb/s. Reset the powered switch for 5 to 10 seconds, wait for factory-ready indication, then adopt it at **UniFi Devices**. Set its uplink to native Bunker with all VLANs allowed. Next connect the PDU management port to a selected 1 GbE Bunker access port, reset/adopt it, and immediately verify PDU outlets 5 and 7 still report enabled and both core devices stayed powered. Finally connect the U7 Pro Max to a selected 2.5 GbE PoE port, reset/adopt it, and set that port to native Bunker with all VLANs allowed. If any device says Managed by Other after ten minutes, repeat that device's physical reset once.

10. **Create YoRHa Wi-Fi.** At **Settings > WiFi > Create New WiFi**, select network YoRHa and only the adopted U7 Pro Max. Set all 2.4, 5, and 6 GHz bands, WPA3 Personal, PMF Required, and MLO enabled. Use the `YoRHa WiFi` 1Password credential. Leave channels, widths, steering, and roaming on Auto until the later RF survey. This Mac reports `802.11ax`, not Wi-Fi 7, so its successful association proves WPA3/6 GHz service but cannot prove MLO negotiation; record MLO separately only if a capable client is at hand.

11. **Pass the bootstrap gate.** Require the UDMP, switch, PDU, and AP to report Online for ten continuous minutes. Require wired YoRHa and YoRHa Wi-Fi to obtain DHCP, resolve DNS, and reach the Internet. Do not move fiber if any device remains Adopting, Updating, Managed by Other, or Offline.

12. **Exercise the zone policy.** Record the Mac's YoRHa address without committing it, reach the AP's Bunker address from the Mac, then run a temporary listener:

   ```sh
   python3 -m http.server 18080 --bind YORHA_MAC_IP >/tmp/yorha-policy-test.log 2>&1 &
   listener_pid=$!
   ```

   Open **UniFi Devices > U7 Pro Max > Settings > Debug**, then from the AP shell run:

   ```sh
   wget -T 3 -O- http://YORHA_MAC_IP:18080/
   ```

   The Bunker-originated request must time out or be rejected, and the `Bunker to YoRHa` block-policy counter must increase. Stop the listener with `kill "$listener_pid"`. A failed request without a policy-counter increase is inconclusive because the Mac firewall could have rejected it; diagnose before PON work.

### Phase 2: prepare the direct WAN without moving fiber

1. **Create port 10 as the dormant direct WAN.** Insert the WAS-110 into UDMP port 10 with its fiber disconnected. At **Settings > Internet**, assign physical port 10 as a DHCP Internet source named `WAS-110`; keep port 9 preferred until all preparation passes. Enable MAC clone and enter the concealed BGW620 WAN MAC from `AT&T Router`. Require the live link to report 10 Gb/s full duplex. The completed cutover later showed that the controller retained Auto negotiation with no port override while satisfying that link requirement, so do not add an unproven forced-speed write merely to restate the negotiated result. Never clone the MAC onto port 9 or a LAN port.

2. **Create the LCT interface route.** At Network 9.4 or later open **Settings > Policy Table > Create New Policy > Route**. On 9.3 use **Settings > Policy Engine > Policy-Based Routes > Create Route**; on 9.2 or earlier use **Settings > Routing > Static Routes**. Set name `WAS-110`, device Gateway, type Interface, value the physical port 10 Internet source, and destination `192.168.11.0/24`.

3. **Prove the Ethernet management boundary first.** Open `https://192.168.11.1` through YoRHa. If it does not respond with fiber absent, identify the actual UDMP interface over SSH rather than assuming a Linux name:

   ```sh
   ssh root@10.10.20.1
   ip -br link
   ip -br addr
   ip route
   ethtool WAN_IF
   ```

   Correlate `WAN_IF` to physical port 10 in Port Manager. Require `Speed: 10000Mb/s`, full duplex, and `Link detected: yes`. Correct the interface route or reseat the stick once; never move fiber while LCT or the 10G host link is absent.

4. **Apply the BGW620 profile.** In LuCI open `https://192.168.11.1/cgi-bin/luci/admin/8311/config` as `root` and enter values directly from 1Password:

   - **PON:** supplied BGW620 ONT ID; Equipment ID `iONT620700X`; Hardware Version `BGW620-700_2.5`; both software fields `BGW620_<captured software version>`; Sync Circuit Pack Version enabled; MIB file `/etc/mibs/prx300_1U.ini`.
   - **ISP Fixes:** Fix VLANs enabled.
   - **Device:** Ethtool Speed Settings `10000`.

   Save and reboot the stick. Do not factory-reset it and do not use one-bank U-Boot edits. Wait up to 15 minutes for LCT and 10G/full host link to return.

5. **Take the no-fiber baseline.** From the Mac, use the legacy SSH algorithms required by this stick and require firmware v2.8.3, a responsive shell, and `eth0_0` at 10G. PON should report no optical service because fiber is still in the BGW:

   ```sh
   ssh -oHostKeyAlgorithms=+ssh-rsa -oPubkeyAcceptedKeyTypes=+ssh-rsa root@192.168.11.1 '
     cat /etc/8311_version
     pontop -b -g s
     pontop -b -g w
     ethtool eth0_0
   '
   ```

6. **Arm the transition.** In **Settings > Internet**, change failover priority so port 10 `WAS-110` is preferred and port 9 `BGW620` is fallback. With no fiber on port 10, UniFi must continue using healthy port 9. This is prepared rollback, not simultaneous optical redundancy; port 9 cannot recover direct service until the single fiber returns to the BGW.

### Phase 3: move fiber and validate each layer

1. **Move fiber once.** Do not look into or touch the end face. Remove the SC/APC connector from the BGW620, protect the vacated receptacle, insert it fully into the WAS-110, and start the 15-minute PON timer. Leave BGW Ethernet connected to port 9 for now, though it has no optical service.

2. **Validate optics and PLOAM before DHCP.** Open `https://192.168.11.1/cgi-bin/luci/admin/status/overview`. Require **PON PLOAM Status: O5.1, Associated**, no active LOS/LODS alarm, and at least fair optical readings. PON.wiki rates Tx 2 through 7 dBm and Rx -27 through -8 dBm as fair or better; values outside those operating ranges stop the cutover. O7 is an emergency/rogue state: remove fiber immediately and roll back rather than reconnecting repeatedly.

3. **Reject fake O5.** Open `https://192.168.11.1/cgi-bin/luci/admin/8311/vlans`. The VLAN Tables text must contain meaningful extended VLAN entries. Blank output, `No Extended VLAN Tables Detected`, or only deceptive defaults fails the PON gate regardless of O5.1. Capture a local diagnostic if needed:

   ```sh
   mkdir -p /tmp/new-house-internet-cutover
   ssh -oHostKeyAlgorithms=+ssh-rsa -oPubkeyAcceptedKeyTypes=+ssh-rsa root@192.168.11.1 '
     date
     pontop -b -g s
     pontop -b -g "Optical Interface Status"
     pontop -b -g w
     ethtool eth0_0
     8311 -extvlan-decode.sh -t
     omci_pipe.sh md | grep -E "^\|\s+(84|171)\s+\|"
     omci_pipe.sh meg 131 0
   ' > /tmp/new-house-internet-cutover/was-110-gate.log
   ```

   The local file may contain live identifiers. Never add it to Git or paste it into chat without redaction.

4. **Validate the host boundary.** On the UDMP, identify port 10's Linux interface and inspect it:

   ```sh
   ip -br link
   ip -br addr
   ip route
   ethtool WAN_IF
   ip -s link show dev WAN_IF
   journalctl -k -b --no-pager | grep -Ei 'WAN_IF|sfp|link|dhcp|udhcpc|udapi'
   ```

   Require 10G/full/link detected with no continuing link transitions. Keep the actual public address and MAC out of notes.

5. **Validate DHCP only after the earlier gates pass.** At **Settings > Internet > WAS-110**, require port 10 to hold an IPv4 lease that is not RFC 1918 (`10/8`, `172.16/12`, `192.168/16`), link-local (`169.254/16`), or CGNAT (`100.64/10`). Do not record the address. If no lease appears after five minutes, save the PON and host snapshots, use the Internet panel's DHCP Renew/Reconnect action once, and wait five more minutes. Then roll back. Do not reboot, reseat, or rewrite the ONT profile to cure DHCP.

6. **Validate direct service.** Confirm UniFi names port 10 as the active Internet path. From wired YoRHa require:

   ```sh
   ping -c 5 1.1.1.1
   dig +short example.com
   curl -4 --fail --silent --output /dev/null https://example.com/
   ```

   Reconfirm LCT reachability at `192.168.11.1`. Failure with O5.1, valid VLAN tables, 10G, and a public lease is now a routing/DNS policy failure, not a PON identity failure.

7. **Remove the hidden fallback before acceptance tests.** Physically disconnect the BGW Ethernet cable from UDMP port 9. Confirm port 10 remains active and repeat wired Internet and LCT checks.

8. **Pass the speed gate.** Run the UDMP gateway speed test from the Network Internet health panel. Both downstream and upstream must reach at least 80 percent of the recorded BGW gateway baseline and remain compatible with the subscribed tier. If the BGW baseline materially exceeds 1 Gb/s, a direct result capped around 1 Gb/s fails even if ordinary browsing works; recheck port 10 and port 11 link speed before blaming PON.

9. **Hold stability for ten minutes.** From wired YoRHa run:

   ```sh
   ping -c 600 -i 1 1.1.1
   ```

   Require zero sustained outage, no WAN failover, O5.1 still associated, valid VLAN tables, and 10G link afterward.

10. **Run the only reboot test.** In console **Settings > Control Plane > Console**, choose Restart. Do not reconnect port 9. The reboot power-cycles the UDMP host boundary and the stick, so wait the full 15 minutes without intervention. Then require, in order: local console login, port 10 10G/full, LCT reachable, acceptable optics, O5.1, meaningful extended VLAN tables, the direct public lease, DNS, Internet, and a shorter confirming speed test. If any layer fails, capture it once and roll back immediately. A second reboot is prohibited because it would fail the recovery requirement even if service returned.

11. **Retire temporary rollback state after success.** At **Settings > Internet**, remove or disable the port 9 `BGW620` Internet definition. Keep ports 1 and 2 as Bunker and YoRHa recovery access. Power down and store the BGW620 with its fiber receptacle protected, Ethernet cable, and its `192.168.10.254` and credential record in 1Password. Do not restore its original subnet merely for storage.

### Rollback procedure

Rollback always starts by preserving the failed layer. Do not reboot or reseat first unless the timeout table explicitly permits it.

1. Record wall-clock time and classify the highest gate that passed: LCT/10G, optics, O5.1, VLAN tables, DHCP, routing, speed, or reboot recovery.
2. If reachable, save the WAS and UDMP read-only snapshots above to `/tmp/new-house-internet-cutover`; do not expose their raw contents.
3. Remove fiber from the WAS-110, protect its connector/receptacle, and insert fiber into the BGW620.
4. Reconnect BGW Ethernet to UDMP port 9 if the final-isolation step had removed it. Port 9 remains the configured fallback until final acceptance.
5. Wait up to 15 minutes. Require the BGW dashboard at `http://192.168.10.254` to show fiber operational, UniFi to select port 9, and wired YoRHa Internet to return.
6. If port 9 does not restore management, join the retained BGW Wi-Fi directly and inspect **Broadband > Status** and **Diagnostics > Troubleshoot**. Restore supplied-gateway service before any more WAS-110 work. Do not alternate fiber repeatedly between two unclassified failures.

### Sources

- [Ubiquiti UDM Pro Quick Start Guide](https://dl-origin.ubnt.com/qsg/UDM-Pro/UDM-Pro_EN.html), physical ports 9, 10, and 11
- [Ubiquiti factory reset guidance](https://help.ui.com/hc/en-us/articles/205143490-How-to-Reset-UniFi-Devices-to-Factory-Defaults)
- [Ubiquiti backups and migration](https://help.ui.com/hc/en-us/articles/360008976393-Backups-and-Migration-in-UniFi)
- [Ubiquiti local administrator management](https://help.ui.com/hc/en-us/articles/28692158912279-Adding-Admins-in-UniFi)
- [Ubiquiti SSH and Debug Console](https://help.ui.com/hc/en-us/articles/204909374-Connecting-to-UniFi-with-Debug-Tools-SSH)
- [Ubiquiti virtual networks](https://help.ui.com/hc/en-us/articles/9761080275607-UniFi-Network-Creating-Virtual-Networks-VLANs)
- [Ubiquiti Wi-Fi creation and settings](https://help.ui.com/hc/en-us/articles/26136823938583-Creating-UniFi-WiFi-SSIDs) and [SSID/AP settings](https://help.ui.com/hc/en-us/articles/32065480092951-UniFi-WiFi-SSID-and-AP-Settings-Overview)
- [Ubiquiti zone-based firewalling](https://help.ui.com/hc/en-us/articles/115003173168-Zone-Based-Firewalls-in-UniFi)
- [Ubiquiti WAN failover and port remapping](https://help.ui.com/hc/en-us/articles/360052548713-WAN-Failover-Load-Balancing-and-Port-Remapping-on-UniFi-Gateways)
- [PON.wiki BGW620-700 profile](https://pon.wiki/guides/masquerade-as-the-att-inc-bgw620-700-with-the-was-110/)
- [PON.wiki WAS-110 connectivity troubleshooting](https://pon.wiki/guides/troubleshoot-connectivity-issues-with-the-was-110-or-x-onu-sfpp/)
- [BGW620/WAS-110 profile research](../research/bgw620-was110-profile.md)
