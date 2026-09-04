# Loch Highland House

## Destination

The new house is livable the way I want it and the old house is sold: every item captured here is either done, decided, or consciously dropped. Distinct from the Bunker Rebuild and the Internet cutover, which own the machines and the network; this map owns the house those machines sit in.

## Notes

- Execution is in scope. This is a living backlog as much as a map: tickets group related chores under one question, and pure chores are `task` tickets. Add items to the ticket they belong to; add a ticket when nothing fits.
- Charted 2026-09-01 from a raw list, one week after the move. Not grilled: the items are captured in Thurston's words, questions sharpened as tickets get picked up.
- Cross-map links: network is in [New-house Internet cutover](../new-house-internet-cutover/map.md) (done) and Bunker Rebuild's [WiFi coverage survey](../bunker-rebuild/tickets/21-wifi-coverage-and-tuning.md); the eGPU decision is Bunker Rebuild's [eGPU enclosure qualification](../bunker-rebuild/tickets/22-egpu-enclosure-qualification.md); the smart-home rebuild (HAOS under incus) belongs to Bunker Rebuild's Phase 4.
- Standing preferences: prefer local-first smart devices that keep working without HA (Matter over Thread bindings); ubiquiti-native where a ubiquiti option exists; get professional help for lighting rather than repeating the can-light mistake.
- Trades to coordinate: electrician (one consolidated scope), hood/duct contractor, gas plumber, TV mounters (The TV Mount Men), Wellbourne (old house door), cleaners, painters.
- Hard dates: moving boxes review **2026-12-01**; laundry blocked until the gas line lands.

## Decisions so far

<!-- one line per closed ticket -->

- [Smart blackout blinds](tickets/06-smart-blinds.md): trial one SmartWings Matter-over-Thread shade on an ordinary window; skylights need model-matched VELUX or tracked SmartWings/Somfy; the odd window needs shape-specific Hunter Douglas or Lutron/Somfy quotes. Lutron stays the reliability baseline; IKEA, Eve, SwitchBot, and Serena can't do skylights or non-rectangular openings. Measure before pricing — checklist in [the research](research/smart-blinds.md).
- [Smart switch and sensor landscape](tickets/23-switch-and-sensor-landscape.md): **Inovelli Blue (Zigbee) binding is the shipping "lights work with HA down" path; Inovelli White's Matter binding exists in firmware/spec but HA cannot configure it yet** — the Matter-over-Thread resilience story is aspirational for an HA-only house today. Apple Thread hubs suffice for HA's Matter access; SkyConnect can join as a manual OTBR. Hue motion = PIR sensors or Bridge Pro radio sensing. Presence Pro = local ESPHome over Wi-Fi/Ethernet, PIR + dual mmWave. Details in [the research](research/switch-and-sensor-landscape.md).
- [Lighting primer](tickets/22-lighting-primer.md): separately controlled ambient/task/accent layers are the whole game; the can-light house failed on a single undifferentiated layer, not on cans per se. Reserve high-CRI fixed-white (Yuji-class) for visual work and reading; Hue gradients/wall-wash only as mock-up-verified accents (their promo look outruns their measured output). Outdoors: warm, shielded, on-demand. Ends with questions for a lighting designer — [the research](research/lighting-primer.md).
- [Garden hose install on cedar siding](tickets/21-garden-hose-install.md): four lags through the Eley 1041 plate into two 16"-on-center studs, with rigid pass-through spacers sealed at the sheathing so the cedar carries no clamp load. Find studs from inside and transfer, then prove with pilot holes; a flashed platform only if framing isn't 16". A filled 125' setup is ~55 lb before hose-pull loads, which is why it's lags, not screws. Procedure and shopping list in [the research](research/garden-hose-install.md).
- [Basement dehumidifier sizing and maintenance](tickets/24-dehumidifier-sizing.md): start with a current DOE-rated 50-pint ENERGY STAR portable on gravity drain for an open basement under ~2,000 sq ft; escalate to ducted/professional only for severe load, divided rooms, or noise isolation (~$1,200–1,800 premium). Continuous drain removes bucket-carrying and nothing else: filters, coils, drain-hose biofilm, flow checks, and RH verification stay recurring. Fill-in sizing worksheet and maintenance calendar in [the research](research/dehumidifier-sizing.md).
- [Sit-stand desk](tickets/25-sit-stand-desk.md): Deskhaus Apex Pro frame + 60×30 hardwood top for maximum standing-height stability and load margin; UPLIFT V2 Commercial (now V3 on their site) is the safer turnkey pick — its crossbar has *measured* lateral-stability benefit (BTOD WobbleMeter) and free 30-day returns. Secretlab wins cable management; Ergonofis, Branch, and Herman Miller's Jarvis lose on price, stability evidence, or warranty. Pre-order measurement checklist in [the research](research/sit-stand-desk.md).
- [Loch Highland Atlas](tickets/26-atlas.md): annotated plans app, built in its own repo `thurstonsand/loch-highland-atlas` on Lakebed; feeds the electrician scope, lighting wiring audit, and sprinkler tickets

## Not yet specified

- Whole-house smart-home rebuild design (automations as code, device inventory keep/drop from the pre-move HA worksheet) — belongs to Bunker Rebuild Phase 4 but the device-side choices here (switches, blinds, sensors, sprinklers, locks, cameras) feed it.
- Omarchy dual-boot laptop setup as a repo-declared host — own effort once the eGPU is qualified.
- Old-house sale timeline: listing date and what "ready to sell" requires beyond the prep list.

## Out of scope

- Server, storage, and network configuration — Bunker Rebuild and the Internet cutover.
