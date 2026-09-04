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

Decide the protocol stack (Thread/Matter vs Zigbee vs mixed), the switch model, and where sensors live. Ties to [Lighting design](04-lighting-design.md) and the smart-home rebuild (HAOS returns under incus per Bunker Rebuild).
