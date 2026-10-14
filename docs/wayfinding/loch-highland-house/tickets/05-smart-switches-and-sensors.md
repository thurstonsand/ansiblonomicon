---
status: open
type: grilling
blocked-by: []
---

# Smart switches and sensors

## Question

The device strategy has settled into three lanes:

- **Hue** for color lighting
- **UniFi SuperLink** for security sensors
- **Matter**, over Thread or Wi-Fi as appropriate, as the catch-all for everything else

The remaining switch question is how wall controls preserve ordinary local operation across the Hue and Matter lanes. Inovelli White remains the Matter-over-Thread candidate; Inovelli Blue, hidden relays, and Lutron are alternatives only where the chosen lane cannot provide the required behavior. Two **Everything Smart Technology Presence Pro** sensors (PIR + mmWave) are still untested.

**UniFi SuperLink** is the installed trial system for exterior-door contacts and motion, and the leading candidate for smoke/CO alarms. The house already has many UniFi cameras and Protect, so this adds one SuperLink Gateway and radio rather than a new software ecosystem. It may earn that extra radio through long-range, low-power sub-GHz coverage, local push into Protect and Home Assistant, first-class Alarm Manager events, and one gateway shared by entry, motion/environment, glass-break, siren, and smoke/CO devices.

Home Assistant, Hue lighting, and Apple Home are set up. The SuperLink Gateway is adopted into Protect through a declared Bunker PoE switch port. Front Door and Basement Door entry sensors are adopted and exposed to Home Assistant beside their corresponding locks; the motion sensor still needs placement and naming. The first live automation locks a Schlage lock only after its sensor reports the door closed. The basic path works, while the longer-run acceptance question remains whether its latency and reliability hold up over repeated use.

- For the doors, reliability and tail latency outrank protocol purity. Trial one UniFi Entry sensor on the metal front door and measure physical close → HA state → Schlage lock action over 50–100 cycles, including outliers; healthy reports suggest sub-second propagation, but anecdotes are not acceptance evidence. Use Eve Matter-over-Thread only if the trial shows Protect/SuperLink delays or reliability problems. Coordinate the resulting close-then-lock behavior with [Locks and entry](08-locks-and-entry.md).
- For smoke/CO, the UniFi alarm's value is supplementary visibility and response: exact detector location, remote alerts, Alarm Manager/webhook actions, Home Assistant automations, and optional AI Speaker announcements. Keep detection and audible life-safety behavior independent of Protect, HA, the gateway, the LAN, and the Internet. Automations such as lights on and HVAC off may react to an alarm; they must never carry the alarm between detectors.
- USL-Smoke-US now explicitly claims UL 217 and UL 2034 certification, so it is not merely a European-certified alarm. Accept Ubiquiti's advertised daisy-chain connectivity as sufficient for selection rather than holding up the decision for more documentation. During commissioning, confirm the shipping units bear an NRTL listing mark, trigger each alarm, and verify every alarm sounds without HA automations.
- USL-Smoke-US has no hardwired option: no 120 V input, PoE, or wired interconnect. The existing alarm locations have power wiring, but the installed units are battery-only. Neither fact establishes that battery-only replacement is permitted. Have the electrician identify whether that wiring is live 120 V alarm power with an interconnect conductor, then ask the inspector for the permitting jurisdiction whether listed, battery-powered, wirelessly interconnected alarms may replace them, or whether wired power must be restored, including in light of the planned electrical work. The governing sections are 2024 IRC R310.6 for power and R310.4 for interconnection. If wired power is required, UniFi remains supplemental coverage and smart observation beside a listed hardwired layer.

The [initial smoke and CO candidate screen](../research/smoke-co-candidate-screen.md) also evaluates Owl Wired, Phare C1, Gentex PLACE Any Space, and Sensereo MSC-1 against the same safety gate. UniFi is the preferred smart candidate and PLACE remains the strongest documented hardwired alternative. The final replacement decision depends on the existing wiring and applicable power-source requirements, not further paper investigation of UniFi's daisy-chain claim. Owl, Phare, and Sensereo do not currently qualify as the house's primary US alarm system, regardless of their more interesting smart features.

Decide the wall-switch model, where sensors live, and which independently listed smoke/CO system or layered combination preserves whole-house alarm behavior while providing useful smart observation. Ties to [Lighting design](04-lighting-design.md) and the smart-home rebuild (HAOS returns under incus per Bunker Rebuild).
