---
status: closed
type: research
blocked-by: []
claimed: 2b-session
---

# Smart switch and sensor landscape

## Question

Research input for [Smart switches and sensors](05-smart-switches-and-sensors.md). Bound with primary sources: Inovelli **White** (Matter over Thread) — shipping status, binding directly to Matter bulbs without a hub, known limitations; Inovelli **Blue** (Zigbee) and the motion-sensor variants; Hue's motion-detecting bulbs/fixtures; Everything Smart Technology's **Presence Pro** (PIR+mmWave) — integration path (ESPHome/HA) and requirements; the state of Matter-over-Thread binding in Home Assistant and whether Thread border routers already owned (HomePods, Apple TV, SkyConnect) suffice. Produce a comparison the decision can be made from, no recommendation required.

## Resolution

[Smart switch and sensor landscape](../research/switch-and-sensor-landscape.md) finds that shipping Blue Zigbee bindings provide HA-down bulb control, while White's Matter binding is firmware/spec-capable but not configurable through HA today. Existing Thread-capable Apple hubs suffice for normal HA Matter access; SkyConnect can join as an OTBR after manual setup. Hue covers PIR or Bridge Pro radio-motion sensing, while Presence Pro supplies local ESPHome PIR plus dual-mmWave sensing but depends on HA for HA automations.
