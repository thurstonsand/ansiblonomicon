---
status: closed
type: implementation
blocked-by: [34, 44]
---

# Minimum Incus and fresh Home Assistant substrate

## Scope override

On 2026-09-09 the user explicitly brought one blank Home Assistant OS VM into the Bunker rebuild. This overrides the map's earlier smart-home exclusion only for the shared substrate and fresh VM described here. Restored state, USB devices, Nabu Casa automation, Home Assistant configuration, and ticket 41's pascal/worker platform remain out of scope.

## Desired state

- Debian stable supplies Incus 6.0 LTS and its dependency closure. Its enabled socket activates Incus after `zfs-mount.service` and the `black-box/incus` mount, and `thurstonsand` belongs to `incus-admin`. The indirect daemon unit is deliberately not managed or restarted: the socket and startup service own activation, while a future start consumes the storage dependency without interrupting a running guest.
- Verified dataset `black-box/incus`, mounted at `/mnt/black-box/incus`, backs the Incus `black-box` dir pool and has the standard non-recursive Sanoid policy.
- Managed macvlan network `scanners` uses parent `enp5s0` and VLAN 40. The host remains untagged Bunker, has no bridge, and cannot directly reach the guest by design.
- `home-assistant` is an x86_64 VM with four CPUs, 8 GiB memory, a 64 GiB sparse root disk on `black-box`, UEFI without Secure Boot, autostart, and one `scanners` NIC with MAC `00:16:3e:48:41:42`.
- First creation imports the checksum-pinned HAOS 18.2 KVM qcow2 as a split Incus image and removes the transient image. Existing VMs are converged safely and never reseeded for seed-version changes; incompatible identity or root storage fails without replacement.
- UniFi port 17 uses a dedicated profile with native Bunker and only tagged Scanners. UniFi reserves `home-assistant` at `10.10.40.42` with matching local DNS.

## Implementation and acceptance

Native `incus` reconciliation has apply and non-mutating check modes. The live verifier covers package version, enabled socket, running service, KVM, pool, network, VM declaration, and running state. Repository tests cover check-mode non-mutation, mismatch refusal, exact seed and resource contracts, and capability closure.

Applied on 2026-09-09. UniFi has a clean plan after reserving `10.10.40.42` and assigning port 17 a Bunker-native profile that excludes every tagged network except Scanners. Incus 6.0.4 reports the VM running with the declared resources, and its live check passes. UniFi observes MAC `00:16:3e:48:41:42` as `homeassistant` at `10.10.40.42`; a temporary Scanners-side macvlan fetched `/api/onboarding` and confirmed every onboarding step was incomplete. The test interface was removed.

The follow-up split generic Incus host, storage, and network policy from the Home Assistant workload capability. The running VM moved through Incus into the dedicated `black-box/incus` dataset without changing its UUID, MAC, resources, or UI-owned state. HAOS and `ha core check` passed after restart. Home Assistant owns its application configuration rather than receiving a parallel repo-managed YAML tree; Incus retains a working guest-agent control path for bounded diagnostics and future operations. The third-party HA-MCP integration provides authenticated native administration: Pi and Claude Code use OAuth against its Nabu Casa endpoint, while Homepage and Amp use the Home Assistant long-lived token where those clients require bearer authentication.
