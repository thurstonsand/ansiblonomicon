---
status: open
type: grilling
blocked-by: []
---

# Ethernet, rack, and cellular

## Question

- low-voltage wiring through the contractor: ethernet everywhere plus audio wire; decide which rooms, how many runs, and where they terminate
- server rack: location (basement?), size, what lives in it (pod042, UDMP, switch, GLKVM, PDU)
- cellular coverage is poor throughout the house. A US Mobile trial is testing its three underlying networks before adding hardware
- camera and doorbell drops feed [Cameras and doorbell](09-cameras-and-doorbell.md)

A quote has been received for the low-voltage work; execution is pending. The physical plan lives in [Loch Highland Atlas](26-atlas.md); coordination remains in [Electrician scope of work](01-electrician-scope.md). WiFi layer is already charted in Bunker Rebuild's [WiFi coverage survey](../../bunker-rebuild/tickets/21-wifi-coverage-and-tuning.md).

For cellular, first compare field-test signal outdoors and in representative rooms on US Mobile's Warp, Light Speed, and Dark Star networks. If one has usable outdoor signal but loses it through the house, install an FCC-certified wideband consumer booster: an outdoor donor antenna, coax, amplifier, and indoor antenna. Wi-Fi calling remains the no-hardware baseline; a carrier-specific femtocell is a poor fit while the underlying network is unsettled.

This is DIY-capable, but the house-scale installation is better folded into the low-voltage work. The difficult part is not plugging in the amplifier; it is finding and aiming the donor antenna, routing and weatherproofing coax, grounding correctly, and preserving at least 25 feet of preferably vertical separation from the indoor antenna so the booster does not oscillate or reduce its own gain. Avoid a roof penetration if an eave, wall, or existing mast works. Register the installed booster with the serving carrier as the FCC requires.
