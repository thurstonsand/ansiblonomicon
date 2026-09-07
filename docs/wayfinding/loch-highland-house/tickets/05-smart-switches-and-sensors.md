---
status: open
type: grilling
blocked-by: []
---

# Smart switches and sensors

## Question

Whole-house switch strategy. Leaning all-in on **Matter over Thread**, e.g. Inovelli White, bound directly to smart bulbs so they work without Home Assistant running. Open to alternatives:

- Inovelli Blue (Zigbee) with built-in motion sensing
- Hue bulbs/fixtures with motion detection
- **Everything Smart Technology** sensors: two of their new **Presence Pro** units (combined PIR + mmWave for better overall detection), still untested — test them, possibly as part of the HA setup process
- hidden switches? Lutron (had them; expensive)?

Strongly consider **UniFi SuperLink** for the exterior-door contacts and smoke/CO alarms. The house already has many UniFi cameras and Protect, so this adds one SuperLink Gateway and radio rather than a new software ecosystem. It may earn that extra radio through long-range, low-power sub-GHz coverage, local push into Protect and Home Assistant, first-class Alarm Manager events, and one gateway shared by entry, motion/environment, glass-break, siren, and smoke/CO devices.

- For the doors, reliability and tail latency outrank protocol purity. Trial one UniFi Entry sensor on the metal front door and measure physical close → HA state → Schlage lock action over 50–100 cycles, including outliers; healthy reports suggest sub-second propagation, but anecdotes are not acceptance evidence. Use Eve Matter-over-Thread only if the trial shows Protect/SuperLink delays or reliability problems. Coordinate the resulting close-then-lock behavior with [Locks and entry](08-locks-and-entry.md).
- For smoke/CO, the UniFi alarm's value is supplementary visibility and response: exact detector location, remote alerts, Alarm Manager/webhook actions, Home Assistant automations, and optional AI Speaker announcements. Keep detection and audible life-safety behavior independent of Protect, HA, the gateway, the LAN, and the Internet. Automations such as lights on and HVAC off may react to an alarm; they must never carry the alarm between detectors.
- USL-Smoke-US now explicitly claims UL 217 and UL 2034 certification, so it is not merely a European-certified alarm. Accept Ubiquiti's advertised daisy-chain connectivity as sufficient for selection rather than holding up the decision for more documentation. During commissioning, confirm the shipping units bear an NRTL listing mark, trigger each alarm, and verify every alarm sounds without HA automations. Separately inspect the house's existing 120 V/interconnect wiring and determine the applicable Cobb County replacement requirements before removing a conventional hardwired system.

The [initial smoke and CO candidate screen](../research/smoke-co-candidate-screen.md) also evaluates Owl Wired, Phare C1, Gentex PLACE Any Space, and Sensereo MSC-1 against the same safety gate. UniFi is the preferred smart candidate and PLACE remains the strongest documented hardwired alternative. The final replacement decision depends on the existing wiring and applicable power-source requirements, not further paper investigation of UniFi's daisy-chain claim. Owl, Phare, and Sensereo do not currently qualify as the house's primary US alarm system, regardless of their more interesting smart features.

Decide the protocol stack (Thread/Matter vs Zigbee vs mixed), the switch model, where sensors live, and which independently listed smoke/CO system or layered combination preserves whole-house alarm behavior while providing useful smart observation. Ties to [Lighting design](04-lighting-design.md) and the smart-home rebuild (HAOS returns under incus per Bunker Rebuild).
