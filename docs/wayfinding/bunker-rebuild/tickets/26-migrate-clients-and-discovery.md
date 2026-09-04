---
status: open
type: task
blocked-by: [25]
---

# Migrate approved clients and scoped discovery

## Question

Import the approved old-house client records, broadcast the required Scanners and The Village WLANs, and move devices into their selected trust domains in controlled cohorts. Finish by enabling only the discovery paths the target model requires.

## Work

- Add approved `unifi_client` resources for names and reservations. Import existing live objects before apply and require a zero-change or intentionally additive plan; never recreate randomized or stale client records.
- Store WLAN credentials in 1Password and R2 state only. Choose the narrowest security and radio compatibility supported by each approved client cohort.
- Migrate infrastructure, administrator, household, discovery, and appliance cohorts separately. After each cohort, confirm DHCP, DNS, Internet, intended zone access, and intended denial before moving the next.
- Configure the manual custom mDNS proxy to reflect only selected services between YoRHa and Scanners and between Lunar Tear and Scanners. Keep Bunker and The Village outside the reflection scope.
- Test real discovery behavior for retained Apple, Google, receiver, console, printer, and future Home Assistant paths represented in the approved inventory. Add named unicast policy exceptions only when a captured failure identifies a required protocol and endpoint.
- Restore Transporter WireGuard and Identity VPN material only from verified preserved state. Test its intended administrator reach without broadening ordinary LAN zones.
- Leave fixed-location AP pinning and RF values to [WiFi coverage survey and RF tuning](21-wifi-coverage-and-tuning.md), after every AP reaches its final location.

## Progress

- Created the Scanners WLAN on VLAN 40 as WPA2/WPA3 Personal transition mode across 2.4 and 5 GHz with optional PMF. Its generated credential is held in the `Scanners WiFi` 1Password item and R2 state, never Git. The live WLAN matches the declaration and OpenTofu reports **No changes** after clearing the provider's confirmed AP-group normalization taint.
- Deferred Google Nest Hub after current Google Home onboarding repeatedly failed before network association. No client record or historical fixed address was restored.
- Migrated the historical Bath HomePod into the kitchen on Scanners. Its stable hardware identity matched the backup, and a name-only resource labels it `Apple HomePod - Kitchen` without restoring the old reservation.
- Replaced the reset controller's overly broad automatic mDNS proxy with custom scope. OpenTofu declares that only YoRHa, Lunar Tear, and Scanners participate; Bunker and The Village do not. The unsupported manual remainder is Custom proxy mode with only UniFi's predefined Apple AirPlay group (`_companion-link`, `_appletv-v2`, `_raop`, `_airplay`) and HomeKit group (`_homekit`, `_hap`). From YoRHa, the migrated HomePod advertises `_airplay`, `_raop`, and `_hap`; it did not advertise `_homekit` during the sample. Audio playback and pause control work from the iPhone on YoRHa, and OpenTofu reports **No changes**.

## Completion

All approved clients occupy their selected trust domains, rejected records remain absent, scoped discovery works from YoRHa and Lunar Tear without exposing The Village or Bunker, VPN access is restored or explicitly deferred, and OpenTofu finishes at **No changes** after representative end-to-end tests.
