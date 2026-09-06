---
status: open
type: prototype
blocked-by: [29]
---

# Choose the pod042 remote console path

## Question

Prototype away-from-home access to `pod042-kvm` through both the existing Cloudflare approach and Tailscale. Measure console interaction, reconnect behavior, virtual-media transfer, and SSH throughput, and identify why the current Cloudflare SSH path is unbearably slow rather than treating that result as inevitable.

Choose the usable private path. Prefer a repaired Cloudflare path if it meets the same operating bar without exposing the KVM directly; otherwise choose Tailscale. GL.iNet cloud is not a permanent dependency. Record setup ownership, client requirements, failure behavior, and a fallback when pod042 itself is down.

## Progress

2026-09-05: deferred until the Debian host is running, by user decision; this is not a cutover blocker. The current Cloudflare `home` tunnel is down because its only connector lived on the now-unreachable TrueNAS network, which also means that placement could never provide console access while pod042 is down. Starting the Mac's Tailscale client exposed stale state from before the KVM reset: it tried to use the now-offline former `glkvm` as an exit node and interrupted internet access. Tailscale was stopped, normal routing was verified through `10.10.20.1`, and the saved menu selection was cleared. Any later prototype must first remove the stale exit-node selection without activating it; the KVM needs direct tailnet membership only, not exit-node or subnet-router duties.
