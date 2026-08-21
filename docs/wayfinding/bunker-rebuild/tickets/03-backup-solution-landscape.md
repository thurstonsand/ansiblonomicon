---
status: closed
type: research
claimed: subagent
blocked-by: []
---

# Backup solution landscape

## Question

What are the most common, well-supported, popular backup solutions for home NAS systems — especially ZFS-on-Proxmox hosts — weighted toward ease of administration? Storj has been a beast to manage; the replacement must be simpler.

Survey against primary sources (official docs, pricing pages, source repos):

- ZFS-native replication targets: rsync.net (zfs send), zfs.rent, a friend's box via syncoid.
- Restic/borg/kopia + cheap object storage (Backblaze B2, Wasabi, Hetzner Storage Box) — tooling maturity, ZFS-snapshot integration, restore ergonomics.
- Proxmox Backup Server — what it covers (guests, host?) and what it doesn't (arbitrary datasets?).
- Cost at the relevant scale: the irreplaceable subset is likely well under 2T (`capacity/backup` is 1.15T); note pricing at 1T/2T/5T tiers.
- Administration burden: what runs unattended, how failures surface, restore drill complexity.

Deliver a shortlist (2–3) with tradeoffs; the decision itself belongs to [Cloud backup replacement](04-backup-replacement.md).

## Resolution

Findings and the decision shortlist are in [Offsite backup solution landscape](../research/backup-solution-landscape.md). The replacement remains undecided for [Cloud backup replacement](04-backup-replacement.md).
