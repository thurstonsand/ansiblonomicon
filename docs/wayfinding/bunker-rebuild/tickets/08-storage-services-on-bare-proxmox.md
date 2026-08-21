---
status: closed
type: grilling
blocked-by: []
---

# Storage services on bare Proxmox

## Question

How does the repo take over everything TrueNAS did for storage — the least-known, most load-bearing part of the rebuild?

To settle, with care:

- Scrub schedules, SMART tests, and alerting: smartd + zed + cron as Ansible roles; where alerts land (email? Discord webhook like pod042?).
- Snapshot schedules: sanoid policy per dataset tier (configs vs media).
- Shares: which SMB/NFS consumers actually exist today (verify on the old host before it goes down); samba/nfs roles to replace them. Includes the `performance/pod042` NFS dataset pattern.
- Ansible surface: adopt `community.proxmox` where the middleware is Proxmox's; plain `zfs`/`zpool`/file modules elsewhere. `local.truenas` retires.
- Users/permissions: settled in [Pool fresh start and permissions reset](10-pool-fresh-start.md); this ticket consumes its outcome.
- Optional UI: Cockpit + 45Drives plugins — worth installing, or CLI/Ansible only?

Feeds the repo-restructure fog (playbook rename, inventory changes).

## Resolution

Grilled 2026-08-19, two rounds, grounded in live recon of the TrueNAS host (shares, scrub/SMART/snapshot schedules queried via midclt). Signed off.

**Shares — from first principles, starting at zero.** One SMB share: `media` → `/mnt/ark/media`, admin-tier RW, `force group = media` (ticket 10's tier-2 model), `vfs_fruit` for macOS. SMB is deliberately the only protocol: Windows speaks it natively, Linux mounts it via cifs as well as it would NFS, so one daemon covers the Mac, the future Omarchy/Windows dual-boot laptop, everything. **No NFS server at all** — every export lost its consumer (docker daemon local, pod042 VM dead, `watch` retired into `ark/media`). **No Time Machine** — 1.15T of it was deleted this week and nothing complained. Under-provisioning is the cheap direction: a new share is three lines in the samba role.

**Snapshots — sanoid.** `black-box`: hourly=24, daily=7, monthly=1, recursive with per-dataset template overrides. `ark`: deliberately bare — matches today (capacity has zero snapshot tasks), matches ticket 04's re-derivability doctrine, and avoids pinning freed space on a delete-heavy 14T pool (the 282G log-leak lesson). Accepted consequence, eyes open: no undo window on media deletes.

**Scrub/SMART/zed.** Scrubs as staggered systemd timers per pool (today's 04:00/35-day cadence); smartd short-daily + long-monthly on all disks (today's schedule); zed enabled — it is the hot-spare reflex on plain Debian (TrueNAS middleware did this; without zed the spare is decorative). All three notify through a single `storage-alert` shim script whose destination is [ticket 12](12-alerting-decision.md)'s decision — one file changes when 12 lands, and storage monitoring ships at rebuild regardless.

**No storage UI.** CLI + ansible only; pascal answers status questions. Cockpit noted as a revisit-on-pain-points option, not installed — a UI that can mutate pools invites drift at the layer where drift hurts most.

**Repo shape (the fog collapses).** One playbook `ansible/playbooks/pod042.yml` replacing both `truenas.yml` and the old VM playbook: local-connection + hostname assert, covering zfs maintenance roles, samba, docker + stacks (docker_stack unchanged, daemon local), incus + pascal/worker profiles, caddy, cloudflared. Tags remain the unit of partial reconciliation. `local.truenas` retires whole — plain Debian roles + `community.general.zfs*` where needed. The `lan:` name book migrates from `group_vars/truenas.yml` to the new target's vars. The self-reconcile loop (checkout → `poe pod042` → verify → bounded agent repair) runs against the host, executed by pascal per ticket 07.
