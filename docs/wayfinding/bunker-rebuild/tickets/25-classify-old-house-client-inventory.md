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
- Do not track ordinary Apple clients from the old inventory: their private addresses cycle and the historical records cannot identify durable hardware. HomePods are the explicit exception; retain and name each one as a particular Scanners client after its live identity is verified. Ordinary human-associated Lunar Tear clients need no controller-friendly aliases. Let both unmanaged groups appear and disappear unless a later service gives one stable identity a concrete reservation or policy requirement.
- Do not migrate the Whirlpool oven, Sense energy monitor, Flo by Moen water sensor, Lockly garage smart lock, or U-Tec front-door lock. Their old controller records are discarded.
- HomePods: retain the Study and Bath devices as particular Scanners clients. The historical Bath unit joined Scanners in the kitchen with the same stable hardware identity; a name-only resource now labels it `Apple HomePod - Kitchen` without restoring its old fixed address. The Study unit remains a migration candidate. Do not copy either historical reservation before a live automation or discovery consumer demonstrates that requirement.

## Completion

Every old record has an explicit retain, discard, or unresolved disposition approved by the user. The resulting manifest contains no controller IDs or unrelated secrets and is ready for selective import without changing live client placement.
