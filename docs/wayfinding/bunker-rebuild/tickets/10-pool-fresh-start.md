---
status: closed
type: grilling
blocked-by: []
---

# Pool fresh start and permissions reset

## Question

How fresh does the storage layout get: import the pools as-is, rebuild datasets in place, or recreate the pool entirely?

Established facts (2026-08-19): ZFS cannot shrink a pool or free partial space from one; raidz vdevs cannot be removed. Post-storj-exit data is ~13.3T (watch 12T + backup 1.15T + misc). Proxmox ships OpenZFS 2.4, which supports raidz expansion (grow a raidz vdev one drive at a time; pre-expansion data keeps its old parity ratio until rewritten). The lone hot spare (12.7T usable) cannot hold the data alone.

Branches:

- **Import as-is** — zero work, carries TrueNAS-era permission scars and dataset layout.
- **Dataset-level rebuild** (no new hardware) — clean datasets on the same pool, local send/recv or rsync with fresh ownership/ACL properties, destroy the old. Fixes everything except pool geometry; ~26T free post-exit makes space a non-issue.
- **Full recreation** (buy 2×14T) — fresh 3-wide raidz1 from spare + new drives (~25T usable), migrate, destroy old pool, then raidz-expand with the freed disks to target width. Only path to fresh geometry (ashift, width, encryption-from-birth); ends with 6–7 drives in service.

Also to settle here: the permissions model itself (today's puid 950/pgid 544 docker convention, Plex's 3001 media ownership — what TrueNAS-specific decisions get revisited), pool names, and target dataset layout. Cross-links: [Storage services on bare Proxmox](08-storage-services-on-bare-proxmox.md) (users/permissions bullet defers here), [Cutover runbook](09-cutover-runbook.md) (ordering depends on this choice).

## Resolution

Grilled across three rounds, 2026-08-19. Decisions:

1. **Branch: rebuild in place (Package A).** Keep both pools; create all-new datasets with clean properties, copy data across, destroy the old datasets. Verified on the live host that pool-level state is clean — only local properties are TrueNAS runtime plumbing that resets at import (`altroot`, `cachefile`), deliberate correct choices (`ashift=12`, `autoexpand=on`), and a standard feature-flag set including `raidz_expansion`. All cruft is dataset-level. No drive purchases (drive prices ruled them out).
2. **Parity: raidz1 stays**, 4-wide + hot spare. The spare remains a spare (auto-heal over capacity); it can graduate into the vdev later via raidz expansion (`zpool attach`, OpenZFS 2.3+) when capacity pressure arrives.
3. **No encryption at rest.**
4. **Pool names at import: `ark`** (bulk, was `capacity`) **and `black-box`** (fast NVMe mirror, was `performance`).
5. **Dataset layout** — placement rule: large files on `ark`; application data of any size on `black-box`.
   - `ark/media` (Plex library: movies, tv, podcasts, downloads), `ark/anypod` (its 607G media archive + transcripts), `ark/backup` (timemachine + device backups).
   - `black-box/docker` (every stack's config — the `apps` concept retires, plex folds in), `black-box/agents` (shape decided by [Agent platform on Proxmox](07-agent-platform-on-proxmox.md)), plus anypod's sqlite db (bound into its compose alongside the `ark` media mount).
   - Retired: `watch` (name and grab-bag), `apps`, `home` (chezmoi regenerates dotfiles; rest is dead), `.system`, `ix-apps`, `ix-applications`, `Clawdbot`, `haos-config`, `homeassistant`, `openclaw`, `vm-snapshots`, `storj-node` (post-exit).
6. **Permission model — two tiers, POSIX only, no NFSv4 ACLs anywhere** (`acltype=posix` at most):
   - *Tier 1, service config dirs*: owned by whatever uid the image insists on (ghost's 1000, mosquitto's 1883), declared per stack, applied by Ansible. No boot-script or invented-user workarounds.
   - *Tier 2, shared data*: group `media` (gid 3000) owns access; dirs `chmod 2775` (setgid); containers join via `PGID` or, universally, docker `group_add: [3000]`; `umask 002` where images support it. Samba: `force group = media`. NFS: plain `sec=sys`.
   - *Escape hatch* for a shared-writing image that ignores umask: a POSIX default ACL (`setfacl -d -m g:3000:rw`) on that path only — named, not default.
7. **Spike evidence (OrbStack, 2026-08-19)**: reproduced both failure modes of the current state (uid 950 cannot create in a 3001-owned dir; 3001's 644 files unwritable by 950). Fix proven: with a `2775 root:3000` dir, four distinct uids (950, 3001, 1883, 7777) — including a hardcoded-uid "mosquitto" with only `group_add` — all created and cross-modified files; setgid propagated into container-created subdirectories. Boundary demonstrated: default-umask (022) writers produce group-read-only files, hence the escape hatch.

CONTEXT.md deliberately not updated yet: `ark`/`black-box` describe post-cutover reality; renaming vocabulary while TrueNAS still runs would mislead agents. The cutover runbook carries that update.
