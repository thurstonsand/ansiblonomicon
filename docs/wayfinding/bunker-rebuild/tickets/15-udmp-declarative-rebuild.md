---
status: closed
type: research
blocked-by: [14]
---

# UDMP declarative rebuild

## Question

Can the UDMP be wiped and rebuilt declaratively from this repo — and how much of its config can ansible actually own?

Motivation: years of accumulated cruft; the zone-based (object-oriented) firewall migration always errored for unknown reasons and a fresh start may clear it; the router occasionally breaks down in confusing ways, and manual reset-and-reconfigure has been a nightmare. Automating recovery buys real peace of mind — the same reconcile-from-repo guarantee every other host has.

Branches to settle:

- What's declarable: survey the UniFi API surface / available ansible collections / terraform providers for networks & VLANs, firewall (zone-based!), port forwards, WiFi SSIDs, device fixed IPs, port profiles. What's config-export vs API-driven vs forever-manual.
- The existing `udmp` playbook's approach (nextdns, multicast-querier) as prior art for how this repo already reaches the router.
- Wipe-and-rebuild path: factory reset → adopt → reconcile, sequenced against the physical move (new house = new WAN anyway).
- Zone-based firewall: why did enabling it error before, and does a fresh config clear the path?

Output: what ansible can own (with tooling choice), what stays manual, and whether the wipe is worth it. The rebuild itself would be its own execution ticket.

## Resolution

Researched 2026-08-19. A clean UDMP rebuild is viable, but it is not a literal factory-to-final single command. Put controller objects with lifecycle in a new OpenTofu `terraform/unifi/` tree, using the active `ubiquiti-community/unifi` provider pinned to a hardware-tested version; retain `ansible/playbooks/udmp.yml` only for the UniFi OS layer (NextDNS and any still-needed multicast querier). This matches the repository split: Terraform owns lifecycle and Ansible owns host state. The provider can model the six networks/VLANs, zones/policies, conventional address/port groups, SSIDs, client reservations/aliases, local DNS, profiles, forwards, the `WAS-110` static route, and IPS/honeypot. It does not safely model the target's custom mDNS proxy scope, so that remains a deliberate UI/runbook step unless a version-pinned raw-API spike proves a stable payload.

The official public Network 9.x API is not the owner: its published 9.1/9.4 contracts are API-key-authenticated inventory/telemetry, action, and hotspot-voucher interfaces, without configuration CRUD. Ubiquiti's generated Ansible collection is a generic request wrapper, not idempotent resource modules. Raw local-controller API calls remain the escape hatch for an unmodelled setting, but are unsupported/version-sensitive and must not become an untested second writer.

Wipe only after AT&T has activated and proven the new WAN, with a laptop wired to the UDMP and the supplied gateway retained as rollback. Bootstrap console/account/API key/SSH and the new WAN first; declare and verify the critical `192.168.11.0/24` via-WAN `WAS-110` route before depending on the bypass; reset/re-adopt downstream UniFi devices as required; then apply controller state in dependency order and reapply the OS playbook. Keep a backup for reference/rollback, never restore it on the clean path — it reimports the cruft being removed. A fresh setup bypasses the legacy-to-zone migration, which Ubiquiti documents as a conservative source of redundant rules, but no source proves it cures historical zone/OON enable errors. Treat it as a smoke-tested hypothesis.

Scoped UniFi mDNS Proxy is capable of the required `admin`/`household` ↔ `discovery` reflection and replaces the current unfiltered reflector. It does not answer the separate IGMP-querier need: retain the existing service through the rebuild until a topology-specific, post-reboot Thread/Matter test proves an elected UniFi per-VLAN querier works. The current playbook also configures rather than installs NextDNS, so it must be made complete before it can recover a blank factory-reset router.

Full findings, feature matrix, manual remainder, sequence, evidence, and risks: [UDMP declarative rebuild research](../research/udmp-declarative-rebuild.md).
