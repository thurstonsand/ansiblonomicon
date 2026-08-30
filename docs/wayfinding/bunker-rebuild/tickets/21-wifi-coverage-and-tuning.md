---
status: open
type: task
blocked-by: []
---

# WiFi coverage survey and RF tuning at the new house

## Question

The wireless layer has never been surveyed. It was tuned reactively at the pre-move house, once, on 2026-08-28, and only because the Haiku fans were slow enough over the `baf` integration to be worth chasing. What that chase found argues the whole 2.4GHz layer deserves a deliberate pass at the new house rather than another accident.

### What the pre-move house looked like before tuning

Every one of the three Haiku fans was associated to the wrong access point, and nothing in the UI said so:

| Fan            | Signal  | TX rate    | TX retries                | AP      |
| -------------- | ------- | ---------- | ------------------------- | ------- |
| Living Room    | -77 dBm | **1 Mbps** | 11,147 / 19,057 = **58%** | Garage  |
| Study          | -70 dBm | 21.7 Mbps  | 22,256 / 121,580 = 18%    | Garage  |
| Master Bedroom | -60 dBm | 14.4 Mbps  | 545 / 2,229 = 24%         | Kitchen |

Two causes, both invisible without pulling the API:

- **`minrate_ng_data_rate_kbps: 1000`** on the IoT SSID. A 1 Mbps floor is no floor, so a client could rot at the slowest rate 802.11 defines and never be pushed to find a better AP. The Living Room fan did exactly that. At 1 Mbps a small frame holds the channel roughly a hundred times longer than at 65 Mbps, and it held it again on every one of its 58% retries.
- **TX power spread of 9 dB between neighbouring APs** (Garage `auto` → 23 dBm, Kitchen `auto` → 23, Bedroom `medium` → 14). The Garage AP was shouting across the house and holding clients that belonged to closer APs.

### What the fix produced

Raising the floor to 12 Mbps and pinning Garage 2.4GHz to a custom 17 dBm moved all three fans to the correct AP:

| Fan            | Signal        | TX rate              | AP                |
| -------------- | ------------- | -------------------- | ----------------- |
| Living Room    | -77 → **-55** | 1 → **65 Mbps**      | Garage → Kitchen  |
| Study          | -70 → **-52** | 21.7 → **57.8 Mbps** | Garage → Kitchen  |
| Master Bedroom | -60 → **-37** | 14.4 → **57.8 Mbps** | Kitchen → Bedroom |

Channel utilization fell on all three radios despite only one being touched, because the 1 Mbps client left the air. Garage's own transmit share went 38% → 12%, Kitchen 22% → 12%, Bedroom 18% → 14%. The Fi Collar Hub, the only other client under the new floor, went 7.2 → 57.8 Mbps for free.

The lesson is not the numbers, which belong to a house being left behind. It is that a single badly-associated client degraded an entire channel for everyone on it, silently, for as long as the fans have been installed, and the only reason it surfaced was an unrelated complaint about a ceiling fan feeling sluggish.

### The tune did not hold, and that is the real finding

Re-measured 2026-08-29, 33 hours later. All three settings were still in place (min rate 12000, Garage pinned to custom 17 dBm, reservations intact), and two of the three fans had drifted back to worse APs anyway:

| Fan            | Right after tuning | 33 hours later      |
| -------------- | ------------------ | ------------------- |
| Living Room    | -53, Kitchen       | -53, Kitchen (held) |
| Study          | -52, Kitchen       | **-73, Garage**     |
| Master Bedroom | -37, Bedroom       | **-67, Kitchen**    |

Master Bedroom ended up worse than its pre-tuning baseline of -60. `latest_assoc_time` confirms both moved on their own: Study re-associated about 20 hours before the reading, Master Bedroom about 4.5 hours before.

So the dramatic improvement measured on 2026-08-28 was substantially an artifact of the mass re-association the min-rate change forced. Every client reconnected at once and picked the best AP available at that instant. Left alone, the Haiku modules roam on their own judgement and choose badly, and with `bss_transition: false` the APs have no way to suggest otherwise.

The implication for the new house: **a point-in-time RF tune is not a fix for stationary clients that roam badly.** Whatever survey and tuning happens post-move has to be paired with a mechanism that keeps clients where they are put, or it will decay the same way within a day or two and look fine in the moment it is measured.

### The work

Gated on the physical move (2026-08-31) and on the UDMP rebuild, since [UDMP declarative rebuild](15-udmp-declarative-rebuild.md) settled that the controller is wiped and re-declared from OpenTofu at the new house. These settings must land in `terraform/unifi/` as part of that declaration, never by hand in the UI, or the next wipe loses them exactly like this one would have.

Four strands:

1. **Survey before tuning.** Walk the new house with WiFiman (or equivalent) and record actual coverage per band, per room, rather than inferring it from client tables after the fact. The pre-move problem was invisible from the controller; a survey is the thing that would have caught it on day one. Decide what artifact this produces and where it lives.
2. **Tune from the survey.** AP placement first, since power and channel choices are downstream of where the radios physically sit. Then the settings below.
3. **Pin every fixed-location device to its AP.** Decided, not open: anything bolted to the structure has no business roaming, and the 33-hour regression above is what happens when it does. Build the inventory of fixed-location clients first, because it is most of the IoT VLAN and not just the fans — pre-move that list also included the washer, dryer, oven, litter robot, feeder robot, Flo water sensor, ratgdo, Tesla Wall Connector, Sense monitor, Elgato key light, and the smart plugs. Genuinely mobile clients (phones, laptops, the car) must stay unpinned, so the inventory needs a deliberate mobile/fixed split rather than a blanket rule.
4. **Capture the result declaratively**, in the terraform tree, with the reasoning recorded so a future reader knows why a number was chosen rather than inheriting a magic constant. Pins included — an AP pin that lives only in the controller is exactly the kind of state the wipe in ticket 15 destroys silently.

### Settings to carry over, with the reasoning rather than the value

The pre-move values are starting points, not answers. A different floor plan gets different numbers.

- **2.4GHz minimum data rate.** 12 Mbps pre-move. The principle: a floor high enough that a distant client is forced to roam rather than squat, low enough that nothing legitimate is stranded. Verify against the actual client set before committing; check for anything sitting below the candidate floor first, which is how the Fi Collar Hub was caught.
- **TX power parity across neighbouring APs.** The number that mattered was the 9 dB _gap_, not any absolute value. Keep neighbouring 2.4GHz radios within a few dB so none out-shouts its neighbours. Note the asymmetry that makes this dangerous to over-tune: lowering an AP's power does not lower the client's, so it only shrinks the cell. Push too far and clients strand, or links go asymmetric with the AP hearing the client fine and the client unable to hear back.
- **DHCP reservations for every fixed IoT device.** None of the three fans had one. `aiobafi6` reconnects by address, so a lease shuffle costs a stall until the config entry retries. The provider models client reservations per ticket 15.
- **AP pinning for fixed-location devices**, per strand 3. Mechanically this is `fixed_ap_mac` on the controller's client object, with `fixed_ap_enabled` derived from it.

  Good news for the declarative half: the `unifi_client` resource that [UDMP declarative rebuild](15-udmp-declarative-rebuild.md) already selected for reservations and aliases is the same resource that carries pins, so pinning adds an attribute rather than a new ownership surface. `ubiquiti-community/unifi` exposes `fixed_ap_mac` on it and sets `fixed_ap_enabled` itself from whether that MAC is non-empty.

  One version floor to respect: `fixed_ap_mac` arrived with the `unifi_user` → `unifi_client` rename in v0.41.4, so the exact pin ticket 15 requires must be at or above that. The research already targets v0.55.0, which is comfortably clear of it.

- **`dtim_ng: 1`, `bss_transition: false`, `fast_roaming_enabled: false`** were all already correct and are worth preserving deliberately rather than rediscovering. Haiku modules in particular handle 802.11r badly.

### Operational notes from the aborted 2026-08-29 pinning attempt

Pins were applied and then reverted the same evening, because the move made them pointless. The attempt still established three things worth not rediscovering:

- **A pin does not move an already-associated client.** Setting `fixed_ap_enabled` + `fixed_ap_mac` only constrains the _next_ association. Two of the three fans were sitting on the wrong AP at the time and stayed there. Forcing the move needs a `kick-sta` through `POST /cmd/stamgr`, so any pinning run is a two-step apply-then-kick, and terraform will only do the first half. Plan for a deliberate reconnect pass after the apply.
- **A pin cannot be fully cleared through the API.** `fixed_ap_enabled: false` alone is accepted, but sending `fixed_ap_mac` as `""` or `null` is rejected with `api.err.InvalidPayload`. The MAC therefore persists, inert, once ever set.
- **That last point is a live risk for the terraform plan.** The provider derives `fixed_ap_enabled` from whether `fixed_ap_mac` is non-empty, so removing a pin from the config would have it send exactly the empty MAC the controller refuses. Whether `unifi_client` handles unpinning cleanly, or wedges on it, is unverified and should be tested on a throwaway client before any device anyone cares about is pinned.

The pinning approach itself remains **unproven end to end**: the session was aborted between the kick and the verification, so no measurement confirms a pinned Haiku actually lands and stays on its assigned AP. Confirm that first at the new house before building the inventory on top of it.

### Open questions

- What does the survey artifact actually look like, and is a floor plan worth maintaining? A marked-up plan with AP positions and measured coverage is the appealing version, but it is only worth it if something keeps it honest as things move. An unmaintained floor plan is worse than none, because it is believed. Decide whether this is a one-time record that informs placement and is then discarded, or a living artifact with an owner.
- Does the survey want to be repeatable? A one-off walk catches placement problems; a repeatable one catches drift. If repeatable, what is the cheapest capture that is still trustworthy?
- Channel plan for the new house: the pre-move one ran 1 / 6 / 11 across three APs, which is correct in principle, but the neighbouring-network picture at the new address is unknown until measured.
- Where the fixed/mobile boundary actually falls. Some devices are ambiguous — a laptop on a desk is fixed in practice and mobile by nature. The cost of guessing wrong differs by direction: pinning something mobile strands it, while leaving something fixed unpinned only costs the drift this ticket already documented. Bias toward pinning only what physically cannot move.
- Whether pins should be expressed against AP _name_ or MAC in the repo. The provider takes a MAC, which is stable across a controller wipe but changes if an AP is replaced under warranty. A name-to-MAC indirection in the terraform is more legible and survives hardware swaps, at the cost of a lookup.
- Is there a monitoring shape that would have caught the Living Room fan without a human noticing a slow ceiling fan? A standing check on client TX rate or retry percentage is cheap and would have fired months ago. Alerting infrastructure already exists per [Alerting decision](12-alerting-decision.md), so this may be a small addition rather than a new system.

## Output

AP placement decided from measured coverage, the RF settings above chosen and justified for the new house, a fixed/mobile split of the client inventory with every fixed-location device pinned to its AP, all of it declared in `terraform/unifi/` including the pins, and a decision on whether the survey is a one-time record or a maintained artifact.
