# Lighting trial buy list, in three phases

Working reference for [Lighting design](../tickets/04-lighting-design.md) and [Smart switches and sensors](../tickets/05-smart-switches-and-sensors.md). Drafted 2026-09-02 from the [lighting primer](lighting-primer.md) and [switch landscape](switch-and-sensor-landscape.md). Prices are US list at drafting; buy from Amazon where returns are likely.

Standing decisions: **Thread everywhere**; the only Zigbee is sealed inside the Hue bridge. Inovelli White for every switch (no Blue). Dumb high-CRI bulbs wherever color isn't the point. Layer ambient / task / accent on separate control.

Before phase 2: breaker off, pull the vanity switch, look for capped white wires (neutral). Check whether the current switches are toggles or Decora rockers — Inovelli White needs Decora-opening plates.

## Phase 1 — Office (color play; no wiring, no switches)

The fan light stays off. Everything plugs in; Hue fixtures stay on constant power. All Hue fixtures below are Zigbee via bridge (the Play/Signe line has no Thread).

| Item                                                                                                        | Price       | Role                                                                                      | Keep-or-return                                                                                                                                      |
| ----------------------------------------------------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hue Bridge Pro** — alone $99, or the starter kit (Bridge Pro + 3× White & Color A19 + Smart Button) ~$199 | $99–199     | Required: office fixtures are bridge-only; the Entertainment API is the Omarchy-sync path | Kit only if the 3 bulbs have a home (master-bedroom bedside lamps for wind-down/night light); the Smart Button becomes the office door scene toggle |
| Hue Play Floor Lamp, large                                                                                  | ~$150       | Gradient tower at the wall: ambient + accent                                              | Likely keeper; 18 segments                                                                                                                          |
| Hue Signe Gradient Floor                                                                                    | $400        | Same role, brighter, 10 segments                                                          | Compare, probably return                                                                                                                            |
| Hue Play Wall Washer                                                                                        | $230        | Paint the wall behind the camera (depth on calls)                                         | Keep if a wall suits it                                                                                                                             |
| Hue Play Light Bar 2-pack                                                                                   | $190        | Behind the monitor; sync workhorse                                                        | Likely keeper                                                                                                                                       |
| Hue Play Table Lamp                                                                                         | $80         | Desk-corner accent                                                                        | Easy return                                                                                                                                         |
| A dumb desk/reading lamp + **Waveform Centric Home A19** (CCT to match the Elgato, likely 3000K)            | $10–15/bulb | High-CRI task layer                                                                       | Keeper                                                                                                                                              |

Buy-everything ≈ $1,150; realistic keep ≈ $550. Omarchy sync: hook `omarchy-theme-set` → palette → Bridge Pro local API v2 / Entertainment streaming.

## Phase 2 — Master bath + closet (six switches, first dimmers, the CRI taste test)

Layout: entrance 3-gang = vanity / tub chandelier / closet. Shower switch by the shower. Toilet room (separate) = light + vent.

### Bulbs and fixtures

| Location                                                  | Today                                       | Buy                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| --------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Vanity (2 bars, 6× A19 bulbs on E26 medium bases)                                   | Philips 3PM5: 6.5 W, 450 lm, 2700K, non-dim | **Waveform Centric Home A19 3000K** ×6 (~800 lm, modest jump) **or** **Yuji SunWave A19 3000K** 8-pack $212 (1,100 lm — needs the dimmer or it's blinding at 6am). Yuji is the stress test; Waveform is the standard                                                                                                                                                                                                                                                                                                      |
| Tub chandelier (2× E12)                                   | candelabra                                  | **Waveform ModernVintage 95 CRI Candelabra LED Filament** ×2 (E12 base, dimmable version), same CCT as vanity. Confirm the socket is E12 (½" thread) and not E17 intermediate |
| Closet boob light (2× A19)                                | unknown                                     | 1× Waveform + 1× Yuji A19 3000K side by side — the taste test                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Closet integrated ceiling                                 | integrated LED                              | Replace with a bulb-taking flush mount (2× E26, ~$30–60); until then, tolerate the clash                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Shower                                                    | integrated wet-rated puck                   | **Halo HLB** wafer (Cooper), wet-location rated, 90 CRI, selectable CCT set to 3000K, dimmable: HLB4 or HLB6 to match the existing cutout — measure the puck's diameter first (~$25–40). Lithonia WF4/WF6 is the equivalent alternative |
| Toilet-room vent + light (one Nutone combo, two switches) | Nutone fan/light                            | **Panasonic WhisperFit DC with light, FV-0511VFL1** ([Amazon B09738RXB6](https://www.amazon.com/dp/B09738RXB6)) — 5⅝" housing (fits a 2×6 bay), installs from below, no attic access needed (floor above). Fan+light version so both switches keep their loads; LED is 10 W / 700 lm / 3000K / CRI 90 / dimmable. Ships with 4" duct plus a 3" adapter. Vs WhisperCeiling DC (7⅜", 4"/6" duct): identical at 50/80 CFM (<0.3 sone); at 110 CFM the Fit is 1.0 sone vs 0.4, and its 3" path is louder still — run it at 80 |

### Switches

| Switch                                    | Model                                                                                                                                | Notes                                                                                                                                       |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Vanity                                    | Inovelli White dimmer VTM31-SN                                                                                                       | six-bulb dimming test                                                                                                                       |
| Tub chandelier                            | Inovelli White dimmer VTM31-SN                                                                                                       | two small bulbs = low load; **bypass** likely                                                                                               |
| Closet | Inovelli White **dimmer** VTM31-SN, configured to on/off mode | the integrated fixture probably doesn't dim; Inovelli dimmers can be set to switch-only mode until the fixture swap, then flipped to dimming. Multi-tap here = scene control for the whole 3-gang |
| Shower                                    | Inovelli White on/off (or dimmer if night-dim wanted)                                                                                |                                                                                                                                             |
| Toilet-room light (Panasonic's light leg) | Inovelli White dimmer VTM31-SN                                                                                                       | the FV-0511VFL1's LED panel is spec'd dimmable; the night light must be wired separately or left unused                                     |
| Toilet-room vent | **Inovelli White On/Off** VTM30-SN — the humidity sensor is built into the White on/off switch itself (there is no separate "humidity" SKU; the on/off IS it) | humidity-triggered fan, no HA needed; the White on/off **requires a neutral** (the dimmer does not) |
| Plates                                    | **Lutron Claro** (or Leviton Decora Plus) screwless Decora, white: 1× 3-gang (entrance), 1× 2-gang (toilet room), 1× 1-gang (shower) | Current switches are all toggles, so every box needs a Decora plate; Inovelli's own plates are intermittently stocked, not worth waiting on |
| Bypass                                    | Inovelli bypass ×2                                                                                                                   | chandelier; one spare                                                                                                                       |

Phase-2 switch count: 2 dimmers, 2–3 on/off, 1 humidity, 2 bypass.

## Phase 3 — Dining chandelier (dumb, dimmed)

| Item                                               | Notes                                            |
| -------------------------------------------------- | ------------------------------------------------ |
| **Waveform 95 CRI E12 candelabra filament, 2700K** | count the sockets first                          |
| Inovelli White dimmer VTM31-SN ×1                  | whole fixture; bypass if the total load is small |

## Deferred until phases 1–2 have taught you what you like

- Open-plan kitchen/living: one CCT for the whole zone (probably 2700K, kitchen task layer carries brightness); the two hallway cans get high-CRI BR30s
- Vanity sconces flanking the mirror at eye level (fixes the top-only shadowing)
- Outdoor lighting (warm, shielded, on-demand — primer section)

Waveform vs Yuji: Waveform (US, CRI 95, $10–15, every form factor, all dimmable) is the house-standardization catalog; Yuji (CRI 98 SunWave, $20–30, few SKUs, some non-dimmable) is the peak-spectrum reference.
