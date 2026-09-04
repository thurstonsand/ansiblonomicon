---
status: closed
type: grilling
blocked-by: []
claimed: 01a05cfb-8dd1-7255-9615-e02b82b6956c
---

# Bunker and YoRHa bootstrap design

## Question

What exact minimum network should the factory-fresh UDMP create before the WAS-110 cutover?

Decide the Bunker and YoRHa VLAN IDs and non-overlapping subnets, which network owns the controller's untagged recovery path, the laptop's wired access port, DHCP and DNS behavior, the first AP's management port, the new YoRHa SSID and security, and the two zones' initial firewall policy. Preserve the accepted invariant that YoRHa may initiate toward Bunker while Bunker may not initiate toward YoRHa. The result must remain a clean first slice of the six-network target rather than temporary state that later needs undoing.

## Resolution

The permanent network family is **Bunker** for infrastructure, **YoRHa** for administrator devices, **Lunar Tear** for household and guests, **Scanners** for locally discoverable and controllable devices, **The Village** for autonomous appliances, and **Transporter** for VPN clients. These are the canonical names in UniFi, code, and documentation rather than display aliases over semantic keys.

The cutover creates the first two. Bunker is the native untagged network at `10.10.10.0/24`; YoRHa is VLAN 20 at `10.10.20.0/24`. Each gateway is `.1`, `.2` through `.99` remain available for infrastructure or fixed assignments, and DHCP leases use `.100` through `.249`. IPv6 stays disabled for this cutover. The UDMP provides DHCP and DNS forwarding with automatically learned upstream resolvers until the later NextDNS rebuild.

Bunker owns the physical recovery path. One unused UDMP LAN port remains a Bunker access port; the Mac moves to a YoRHa access port after the network and policy exist. Infrastructure trunks use native Bunker and permit every VLAN. This applies to the UDMP-to-switch and switch-to-AP links; SSID configuration, not the trunk allowlist, controls which client networks an AP broadcasts. Ordinary device access ports remain assigned to one network.

UniFi's zone matrix owns baseline trust. YoRHa may initiate toward Bunker and every future home zone; Bunker may not initiate toward YoRHa or future client zones. Both may reach the Gateway services they require and the External zone. Stateful return traffic remains implicit. Object Manager is reserved for later device or network exceptions, routing, application filtering, and QoS rather than replacing the auditable zone-to-zone contract.

The permanent YoRHa SSID uses WPA3 Personal only; its credential remains outside Git. During bootstrap all APs stay disconnected until the old controller state is erased. The clean controller then adopts the UDMP, one PoE switch, the UniFi power device, and one AP before PON cutover.
