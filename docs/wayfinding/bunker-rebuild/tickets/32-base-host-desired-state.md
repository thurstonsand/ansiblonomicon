---
status: closed
type: grilling
blocked-by: [31]
claimed: T-01a0790a-aa41-7258-b0fd-c559a15e473a
---

# Base host desired state

## Question

Audit the old playbook's base-system behavior and decide what the fresh Debian 13 host should actually declare: package and repository policy, upgrades, users and groups, SSH, login shell, time and locale, kernel or hardware prerequisites, reboot behavior, and retired state. Include the minimum bootstrap state needed before the normal native mise reconcile can take over.

Do not preserve a package or setting merely because Ansible once installed it. Close with an explicit accepted inventory and verification contract; then create a separate implementation ticket.

## Resolution

The base capability explicitly retains `intel-microcode`, `locales`, and `systemd-timesyncd` alongside the landing-zone packages, generates only `en_US.UTF-8`, selects `America/New_York`, and requires an active synchronized clock. Fnox and 1Password CLI remain latest-version host tools. SSH remains key-only with root login disabled, 30-second client keepalives, three missed keepalives, and last-login reporting; configuration must pass `sshd -t` before reload.

The journal is persistent and bounded by both 1 GiB and 30 days. Debian's persistent `apt-daily-upgrade.timer` runs unattended upgrades daily against every configured origin. Kernel and ZFS package families are excluded for deliberate reconciliation; automatic reboot and all automatic package or dependency removal remain disabled. Upgrade failure, pending protected updates, and reboot-required state notify Hark through the existing `storage-alert` and `/etc/alerting` contract without success notifications or a custom Netdata collector.

APT removals are exceptional capability-owned retirements: add one explicit idempotent removal to the owning capability, apply it live, then delete that retirement. There is no parallel package-state DSL. UPS and backups remain deferred. The base verifier checks installed packages, locale, synchronized time, SSH policy, journal and upgrade configuration, and timer state; the alerting capability separately owns the Hark integration. [Ticket 48](48-implement-base-host.md) records implementation and live acceptance.
