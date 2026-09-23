# pod042's physical network

`enp5s0` is the only addressed interface. ifupdown raises it from `/etc/network/interfaces` and hands it to dhcpcd; there is no host bridge and no NetworkManager. `check.py` asserts the live contract after reconciliation: MAC, 2.5 Gb/s, MTU 1500, RX ring 4096, the sole DHCP address `10.10.10.42`, one default route through `10.10.10.1`, `10.10.10.1` in the resolver, default-denied forwarding, Tailscale's identity and preferences, and the client VLANs terminating only inside the `probe` namespace.

## The resolver gate

`ifup` starts dhcpcd and returns success when dhcpcd's timeout expires, whether or not a lease arrived. On 2026-09-18 the NIC took 27 seconds to negotiate carrier, dhcpcd timed out three seconds later, and `networking.service` finished with no address, no route and an empty `/etc/resolv.conf`. `network-online.target` activated on that, Docker started one second later, and Docker stamps every container's `/etc/resolv.conf` from the host's file at container start. The lease landed at 12:47:30, fourteen seconds too late: every container Docker had already started carried `# NO EXTERNAL NAMESERVERS DEFINED` for the rest of its life, and nothing noticed for fourteen hours.

`resolver-online.service` closes that window. It is `Before=network-online.target` and `WantedBy` it, the same shape as `ifupdown-wait-online.service`, and `resolver-online.py` polls until the host holds both a default route and a nameserver. Docker, `probe.service` and Incus are ordered after the target and wait for this check without each repeating it.

The gate is bounded at 120 seconds and fails rather than hanging boot. A failed `Wants=` dependency does not block `network-online.target`, so the host still boots, and the failed unit shows up in Netdata's systemd-units alarms instead of in a container's DNS six hours later.

Containers do not test this from here. `containers/check.py` asserts that every running container actually resolves an external name, which is the consequence rather than the ordering.
