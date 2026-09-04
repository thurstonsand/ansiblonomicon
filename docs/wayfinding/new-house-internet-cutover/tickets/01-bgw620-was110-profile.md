---
status: closed
type: research
blocked-by: []
claimed: 01a05cfb-8dd1-7255-9615-e02b82b6956c-research
---

# BGW620 and WAS-110 service profile

## Question

For this live BGW620-700 XGS-PON service and the existing WAS-110 on 8311 community firmware v2.8.3, what exact gateway identity, ONT-emulation, host-link, and UDMP WAN settings must be captured and applied for direct bypass after a factory reset?

Start from the existing Bunker Rebuild fiber-bypass research, then verify the BGW620-specific path against current primary sources and the read-only BGW dashboard. Distinguish the values needed on the WAS-110 from the value cloned onto the UDMP, state how to validate O5 and usable OMCI/VLAN state, and identify which fields are secrets that must not enter the repository. Produce a concise research document that the later cutover ticket can follow without guessing.

## Resolution

[BGW620-700 WAS-110 service profile](../research/bgw620-was110-profile.md) records the source-backed ONT profile, distinct UDMP WAN MAC clone, LCT route, validation gates, safe cutover order, and secret-handling boundary.
