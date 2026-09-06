---
status: closed
type: research
blocked-by: []
claimed: subagent-gl-rm1pe-research
---

# GL-RM1PE capabilities and safe bootstrap

## Question

Establish the facts needed to install the GL.iNet GL-RM1PE as `pod042-kvm` without guessing:

- exact power inputs, PoE standard and power budget, whether one cable from the Pro Max 24 PoE is sufficient, and negotiated Ethernet speed
- required HDMI, USB, and optional ATX-control connections to pod042
- first-boot and factory-reset procedure, including any recovery hazard, firmware channel, and state worth recording before reset
- supported local administration, authentication, updates, configuration backup/export, SSH or API access, and whether any configuration can be safely automated
- supported non-cloud remote paths, especially Tailscale and operation behind Cloudflare Tunnel/Access, including protocols used by console video and virtual media
- security-relevant defaults and hardening steps

Use primary sources: GL.iNet product documentation, manuals, firmware/source repositories, and applicable IEEE or UniFi specifications. Write findings to `research/gl-rm1pe-capabilities.md`, cite every consequential claim, append a linked Resolution here, and close the ticket. Do not modify the map.

## Resolution

[Research completed](../research/gl-rm1pe-capabilities.md). One 1 GbE PoE+ port on the UniFi Pro Max 24 PoE supplies both network and power: the GL-RM1PE supports 802.3af/at, consumes less than 5 W, and cannot use 2.5 GbE. Wire it to `pod042` with HDMI and USB; add the inline GL-ATXPC only for physical power/reset control.

Record the label identity, observed MAC/IP, firmware/channel, bindings, configuration export, and useful virtual media before an authenticated factory reset. Do not hold Reset while applying power because that enters U-Boot recovery. Use current stable firmware, a unique admin password, 2FA, restricted Bunker networking, and no GL.iNet Cloud binding.

The firmware directly supports browser access over Tailscale without GL.iNet Cloud. Cloudflare Tunnel supports the HTTP and WebSocket pieces, but GL.iNet uses WebRTC for normal video and does not document Direct-mode or virtual-media upload transports, so full Cloudflare operation remains explicitly unproven pending the installation prototype.
