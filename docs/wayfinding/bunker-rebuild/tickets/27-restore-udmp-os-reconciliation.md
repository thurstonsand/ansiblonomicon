---
status: closed
type: task
blocked-by: [24]
---

# Restore UDM Pro OS reconciliation

## Question

Make `mise udmp` safe and complete against the factory-reset new-house gateway. The old Ansible inventory targeted retired `192.168.1.1`, while its `nextdns` tag assumed an already-installed binary and service that the clean console did not have.

## Work

- Target the stable YoRHa gateway address without embedding credentials.
- Restore NextDNS from a blank UDM Pro, preserve its firmware-recovery behavior, and use the product's stable-release updater on every reconciliation.
- Render `/data/nextdns.conf`, enable and start the service, and prove gateway clients use the intended NextDNS profile.
- Replace retired `br2`, `br3`, and `br4` multicast-querier assumptions with Bunker, YoRHa, Lunar Tear, Scanners, and The Village bridges. Do not restore the old all-bridge reflector; scoped mDNS belongs to [Migrate approved clients and scoped discovery](26-migrate-clients-and-discovery.md).
- Replace the UDM Pro Ansible target with native mise remote bootstrap and delete the superseded implementation after convergence.

## Resolution

Closed 2026-09-02. `bootstrap/mise.toml` now defines the UDM Pro remote target at `10.10.20.1`, stages `bootstrap/targets/udmp/`, sends the existing `NEXTDNS_PROFILE_ID` only through encrypted SSH environment transport, and runs the system-wide mise executable at `/usr/local/bin/mise`. `mise udmp --update-mise` explicitly refreshes that executable when the target's minimum version advances.

The target composes separate `setup/`, `multicast-querier/`, and `nextdns/` configuration roots. Mise's native privileged-file and system-service resources own the persistent NAS SSH key recovery service, restricted SSH secret input, `/data/nextdns.conf`, and multicast querier on `br0`, `br20`, `br30`, `br40`, and `br50`. The NextDNS bootstrap task covers the unsupported package edge: when no valid binary exists, it resolves GitHub's latest stable release, takes the ARM64 archive checksum from that release's manifest, verifies and installs it, then invokes `nextdns install` from the complete managed configuration. Every reconcile runs the product's built-in `nextdns upgrade` and requires an enabled active service.

Acceptance passed on the live reset console:

- The post-reset ED25519 fingerprint matched the independently retained factory-address key before `known_hosts` was replaced.
- Key-only SSH works through the `NAS SSH Key` held by 1Password, and deleting the live authorized key followed by restarting `ssh-keys-restore.service` restored access from `/data/ssh/`. The temporary GLKVM key is no longer authorized.
- NextDNS 1.47.3 is active, enabled, using DoH and the expected profile; its recovery binary exists.
- `googleads.g.doubleclick.net`, `pagead2.googlesyndication.com`, and `securepubads.g.doubleclick.net` changed from public answers before restoration to `0.0.0.0` afterward.
- The browser-level ad-block test blocked 104 of 132 probes; the remainder includes cosmetic and script behavior outside DNS filtering.
- Every current trust-domain bridge reports `multicast_querier=1`.
- A final `mise udmp --check` reports system files and services already converged and does not execute the custom bootstrap task.

The old `ansible/playbooks/udmp.yml`, target inventory, and UDM group variables were deleted after those gates passed. No retirement task remains. Captive portal testing was not applicable because no current WLAN uses one; the restored configuration retains the prior `detect-captive-portals false` policy.
