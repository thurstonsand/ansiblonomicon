---
status: open
type: task
blocked-by: [24]
claimed: 01a05cfb-8dd1-7255-9615-e02b82b6956c
---

# Classify the old-house client inventory

## Question

Recover the old controller's client records from the encrypted pre-reset backup and compare them with clients observed on the clean controller. Present the user with a reviewable inventory so each real device is deliberately retained, renamed, assigned to Bunker, YoRHa, Lunar Tear, Scanners, or The Village, or discarded. Transporter peers receive the same review from the preserved VPN material.

## Work

- Decrypt and inspect the retained backup locally without printing credentials, WAN identity, ONT identity, public addresses, or unredacted diagnostics.
- Extract client names, hardware addresses, old network, reservation and fixed-address state, historical connection recency, and any AP pin. Treat randomized private client addresses as ephemeral unless evidence proves a stable use.
- Compare backup clients against devices already observed after the reset. Deduplicate renamed devices and distinguish infrastructure hardware from ordinary clients.
- Recommend a destination using the settled model: infrastructure in Bunker, Thurston's devices in YoRHa, household and guests in Lunar Tear, controllable and discoverable devices in Scanners, and autonomous appliances in The Village.
- Review the complete recommendation with the user. Never import a stale, unknown, or ambiguous record by default.
- Produce the smallest declarative manifest needed by `unifi_client`: approved name, stable hardware address, destination network, and reservation only where a stable address has a consumer. Preserve AP-pin candidates for [WiFi coverage survey and RF tuning](21-wifi-coverage-and-tuning.md); do not apply old-house pins in the new floor plan.

## Progress

- Eight Sleep: retain the current Pod 5 as an ordinary The Village WLAN client; discard the older Pod last seen in 2025. A name-only `unifi_client` resource changes its controller label from `eight-pod` to `Eight Sleep Pod 5`; it declares no network override or fixed address. The connected appliance remains on The Village with a VLAN 50 lease and OpenTofu returns **No changes**.
- Do not migrate either historical Roomba, `ratgdo`, the Lutron Caseta Hub, the Flic Hub, the Google Home Max, or the Kitchen, Study, and Master Bedroom thermostats. Their old controller records are discarded.
- Google Nest Hub: defer migration after current Google Home onboarding repeatedly failed before network association. Do not restore its historical fixed address. Keep the live Scanners WLAN for the remaining approved discovery cohort.
- Tesla Model 3: retain as an ordinary The Village WLAN client. Its live hardware identity exactly matches the old `Nausea - Tesla Model 3` record; a name-only `unifi_client` resource restores that label without a reservation, local DNS record, AP pin, or network override. The car remains on a dynamic VLAN 50 lease and OpenTofu reports **No changes**.
- Naming rule: every device of Thurston's gets a name-only `unifi_client` record, whatever network it sits on, so the controller never shows a bare hardware address for something we own. Other people's devices are exempt, which in practice means most of Lunar Tear: guests and household hardware turn over, and naming them is work without a reader. The work laptop lives on Lunar Tear deliberately and is named anyway, because it is Thurston's. A name is still not a reservation; a fixed address or local DNS record waits for a consumer that needs one.
- Do not track ordinary Apple clients from the old inventory: their private addresses cycle and the historical records cannot identify durable hardware. HomePods are the explicit exception; retain and name each one as a particular Scanners client after its live identity is verified. Let unmanaged clients appear and disappear unless a later service gives one stable identity a concrete reservation or policy requirement.
- Do not migrate the Whirlpool oven, Sense energy monitor, Flo by Moen water sensor, Lockly garage smart lock, or U-Tec front-door lock. Their old controller records are discarded.
- HomePods: retain the Study and Bath devices as particular Scanners clients. The historical Bath unit joined Scanners in the kitchen with the same stable hardware identity; a name-only resource now labels it `Apple HomePod - Kitchen` without restoring its old fixed address. The Study unit remains a migration candidate. Do not copy either historical reservation before a live automation or discovery consumer demonstrates that requirement.

- Audited the live controller against the naming rule. Named the Hue bridge `Hue Bridge Pro` to match its switch port and PDU outlet labels, and declared `name` on all four adopted devices so their labels reconcile instead of living only in the controller. Forgot 21 stale client records that carried randomized addresses or belonged to the retired `truenas`; held `84:08:3a:61:fe:81` (`type-a-no2`) and `00:e0:4c:00:0a:9a` (a Realtek USB ethernet adapter reporting `Thurstons-MacBook-Pro`) for identification. OpenTofu reports **No changes** after the purge.
- Two unidentified Espressif boards sit on Lunar Tear at `10.10.30.112` and `10.10.30.236`, associated within three minutes of each other on 2026-09-03 and continuously up since. NextDNS places both at the old house on `192.168.3.x` in August, so they predate the move. Their only traffic is NTP and one AWS IoT Core account, `a2wz9c6y6mikoy.iot.us-east-1.amazonaws.com`, which matches no other device in the profile and no public record. They are appliances on the guest network and need both a destination and a name once identified. Bunker cannot reach them, confirmed by a failed ping and HTTP probe from pod042, so identification has to come from YoRHa. Resolved 2026-09-14: they are the Whisker Feeder-Robot (`3c:61:05:6a:d0:7c`) and Litter-Robot (`c8:c9:a3:c2:36:90`), now named and moved to The Village. Lifting their block exposed [ticket 51](51-unifi-client-blocked-never-reaches-aps.md).
- Thurston's Apple clients use Private Wi-Fi Address, so no name record survives a rejoin. Turning the feature off for the YoRHa SSID on each device is the prerequisite for naming them; the randomized records were purged rather than pinned.

## Completion

Every old record has an explicit retain, discard, or unresolved disposition approved by the user. The resulting manifest contains no controller IDs or unrelated secrets and is ready for selective import without changing live client placement.
