---
status: open
type: grilling
blocked-by: [31]
---

# Host network desired state

## Question

Specify pod042's final network declaration under the completed trust-domain design: physical 2.5 GbE interface, Bunker access-port identity, DHCP reservation or static addressing, DNS, bridge requirements for Docker and Incus, forwarding, firewall ownership, MTU, boot-time failure behavior, and Wake-on-LAN through `pod042-kvm`. Pair WOL with a BIOS decision for power recovery after AC loss and state plainly what remains impossible without the GL-ATXPC board.

The old tagged bridge and macvlan topology is scheduled to retire, so treat it as migration evidence, not desired state. Close with link, routing, isolation, and reboot acceptance tests; then create a separate implementation ticket.
