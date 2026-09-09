---
status: closed
type: implementation
blocked-by: [32]
claimed: T-01a0790a-aa41-7258-b0fd-c559a15e473a
---

# Implement the pod042 base host

## Objective

Implement the accepted [Base host desired state](32-base-host-desired-state.md) through the native `base` capability without invoking the retired Ansible playbook.

## Completion evidence

- [x] Native state declares the accepted packages, locale, timezone, synchronized timesyncd, latest fnox/op tools, SSH policy, and bounded persistent journal.
- [x] SSH configuration is validated before reload and a focused live base verifier runs after reconciliation.
- [x] Debian's persistent daily upgrade timer covers every configured APT origin, excludes kernel and ZFS families, never reboots, and never removes packages or dependencies automatically.
- [x] Upgrade failure, protected updates pending, and reboot-required notifications call the shared Hark shim without success noise.
- [x] Focused tests distinguish protected package families from ordinary upgrades and assert the accepted declaration.
- [x] Keep notification units in the alerting capability, which owns `storage-alert` and its Hark credential contract; the minimum base capability remains independently deployable.
- [x] Apply on pod042 and capture a clean second base plan plus effective SSH, synchronized time, journal, APT policy, and notification-hook readback.

## Implementation state

Applied on 2026-09-09. The focused verifier reports `PASS  base packages, locale, time, SSH, journal, and upgrades`; a second native base plan reports 30 unchanged resources with no creates, updates, removals, or unknowns. `apt-daily-upgrade.service` reads back the Hark `OnFailure` and post-upgrade hooks, and the post-upgrade check exits successfully. Alerting remains a separate capability so base recovery does not depend on secret delivery.
