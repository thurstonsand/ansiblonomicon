---
status: open
type: task
blocked-by: []
---

# Evaluate UniFi 10.6 operations features

## Question

After the existing Official-channel auto-update policy installs UniFi Network 10.6 naturally, evaluate the small set of recent Network features that could improve this single-site home deployment. Enable only features with a concrete benefit, a tested rollback, and no conflict with OpenTofu ownership. Do not manually accelerate application or device updates for this ticket.

Sources:

- [Introducing UniFi Network 10.6](https://blog.ui.com/article/introducing-unifi-network-10-6)
- [Introducing Network 10.5](https://blog.ui.com/article/introducing-network-10-5)
- [Introducing UniFi Network 10.4](https://blog.ui.com/article/introducing-unifi-network-10-4)

## Current update policy

Verified on the live UDM Pro after the new-house cutover:

- UniFi OS auto-update is On on the Official channel.
- Network application auto-update is On on the Official channel.
- Device Auto-Update is enabled.
- Early Access release channels are disabled.

Leave those settings in place. Begin evaluation only after Network 10.6 arrives through that policy and the controller has settled to a zero-change OpenTofu plan.

## Candidates worth evaluating

1. **Port locking for UniFi PoE devices.** Network 10.6 adds `Lock Port to UniFi Device`, gated on switch firmware 7.6 or newer. Evaluate it first on the U7 Pro Max's switch port after the switch reaches the required Official firmware. Prove ordinary AP reboot, reprovision, and replacement recovery before expanding it. Do not lock gateway or switch uplinks merely because the control exists.
2. **Nightly Channel AI.** Evaluate only after [WiFi coverage survey and RF tuning](21-wifi-coverage-and-tuning.md) establishes a measured baseline and the remaining APs are deployed. Compare at least a week of channel choices and client outcomes against the declarative RF plan. Do not enable automation that fights OpenTofu-owned channels or turns a survey into decorative paperwork.
3. **Multicast Suppressor.** Network 10.6 announced it for Early Access and requires UAP 8.8 or newer. Wait for an Official release. Test discovery, mDNS, AirPlay, HomeKit, and IoT behavior across Lunar Tear, Scanners, and The Village before considering it; airtime protection is not useful if discovery quietly dies.
4. **Link Debounce and Auto STP Edge.** Network 10.5 added both. Inspect their live defaults and provider coverage. Test them on known-good access ports, not the suspect switch port 24: debounce must not disguise a physical link fault. Record whether explicit configuration improves convergence or merely restates controller defaults.
5. **IPv6 detection and WireGuard over IPv6.** Network 10.4 added automatic ISP dual-stack detection and IPv6 WireGuard transport. Once the household network design reaches its IPv6 phase, measure AT&T prefix delegation and decide whether YoRHa, Lunar Tear, and Transporter should adopt it. IPv6 remains disabled until that firewall and addressing design exists.

## Features that need no project work

Use Time Machine in client, radio, port, and topology views when troubleshooting; use Topology Spotlight when the estate becomes large enough to warrant it; and rely on SafeOps test-and-confirm rollback when changing supported management settings. These are operational tools rather than configuration targets.

Do not pursue bulk fleet updates, Site Manager Blueprints and Drift Inspector, SAML fleet administration, eBGP, SD-WAN underlays, or the High Availability Readiness score for this single-controller home network unless the topology changes enough to give them a job.

## Completion

- Record the installed Network, switch, and AP versions without forcing an update.
- Evaluate each candidate against its stated prerequisite and record accept, reject, or defer with evidence.
- Put accepted stable configuration in `terraform/unifi/` when the pinned provider fork can round-trip it. Keep unsupported controller state manual and document its exact recovery path.
- Require representative packet or client testing only for the behavior changed, followed by a full **No changes** OpenTofu plan.
