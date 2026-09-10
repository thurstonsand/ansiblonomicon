---
status: closed
type: prototype
blocked-by: [29]
---

# Choose the pod042 remote console path

## Question

Prototype away-from-home access to `pod042-kvm` through both the existing Cloudflare approach and Tailscale. Measure console interaction, reconnect behavior, virtual-media transfer, and SSH throughput, and identify why the current Cloudflare SSH path is unbearably slow rather than treating that result as inevitable.

Choose the usable private path. Prefer a repaired Cloudflare path if it meets the same operating bar without exposing the KVM directly; otherwise choose Tailscale. GL.iNet cloud is not a permanent dependency. Record setup ownership, client requirements, failure behavior, and a fallback when pod042 itself is down.

## Progress

2026-09-05: deferred until the Debian host is running, by user decision; this is not a cutover blocker. The current Cloudflare `home` tunnel is down because its only connector lived on the now-unreachable TrueNAS network, which also means that placement could never provide console access while pod042 is down. Starting the Mac's Tailscale client exposed stale state from before the KVM reset: it tried to use the now-offline former `glkvm` as an exit node and interrupted internet access. Tailscale was stopped, normal routing was verified through `10.10.20.1`, and the saved menu selection was cleared. Any later prototype must first remove the stale exit-node selection without activating it; the KVM needs direct tailnet membership only, not exit-node or subnet-router duties.

2026-09-10: two fresh Amp orbs provided the external test clients. Both first proved that the private `10.10.10.34` address was unreachable. The Cloudflare orb then used the existing Access service identity against dedicated HTTPS and SSH tunnel routes. Ten full status operations passed at 273/318/429 ms minimum/median/maximum; five 2560×1440 screenshots passed at 562/575/1,706 ms; five fresh SSH tunnels reached a valid Dropbear banner at 318/400/487 ms; and two temporary 16 MiB virtual-media uploads sustained roughly 10 MiB/s. Every session and tunnel reconnect passed, and both test images were removed and verified absent.

The Tailscale orb joined as a deliberately route-free client. The KVM itself retained `accept_dns=false`, `accept_routes=false`, no advertised routes, and no exit-node role. The orb environment could not use UDP, so all ten probes relayed through DERP Dallas at 62/63/153 ms rather than establishing a direct path. Even under that pessimistic transport, ten fresh login/status operations passed at 1.874/1.909/2.001 s, five screenshots passed at 2.263/2.292/3.403 s, ten SSH banners arrived at 144/145/148 ms, and a temporary 16 MiB image uploaded at roughly 2 MiB/s before verified removal. A final authenticated call to the KVM's native Wake-on-LAN endpoint returned HTTP 200 in 132 ms for pod042's MAC while the already-running host remained undisturbed.

## Resolution

Tailscale is the primary recovery path. Cloudflare performed better for the web console and virtual media, but its connector runs on pod042 and therefore disappears with the machine it is meant to recover. Tailscale terminates on the independently powered KVM, requires no route, DNS, or exit-node authority, and remained fully usable even through a relay-only orb. Cloudflare remains a useful convenience path while pod042 is healthy, with service identity support for unattended clients. A normal UDP-capable external client may improve Tailscale performance further, but a direct path is not required for recovery.
