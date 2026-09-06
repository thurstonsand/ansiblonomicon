# Three-dataset physical consolidation, 2026-09-06

Deployed and verified on physical pod042 at clean, pushed revision `9e8757b`. The operator approved consolidating the six freshly migrated filesystems into exactly three: `ark/media`, `black-box/docker`, and `black-box/agents`. No application consumer was activated, no retired Ansible ran, and no reboot or sleep-setting change occurred.

## Data and snapshots

AnyPod's archive is now the ordinary directory `/mnt/ark/media/anypod`. AnyPod and Plex remain at `/mnt/black-box/docker/anypod` and `/mnt/black-box/docker/plex`, now ordinary directories inside Docker rather than child datasets. The existing Docker parent content stayed in place.

Sanoid's timer stopped before mutation; snapshot/prune jobs, copy jobs and application consumers were inactive. The root-private inventory recorded 68 dataset GUIDs and 3,778 current snapshot GUIDs. Recursive snapshots `pre-consolidation-20260906T152500Z`, held as `pod042-consolidation`, added 68 snapshots before copying. All 68 dataset GUIDs and all 3,846 resulting snapshot GUIDs survived cutover and the subsequent Sanoid tests. That includes all 60 original dataset GUIDs, 3,758 original snapshot GUIDs, and 20 intervening Sanoid snapshots. Original volume sizes, reservations and refreservations remain unchanged.

| Copy | Regular files | Logical bytes | Content comparisons | All-entry metadata checks |
| --- | ---: | ---: | --- | ---: |
| AnyPod config/database | 6 | 9,863,902 | 6 full SHA256 | 11 paths |
| Plex | 48,896 | 38,859,691,627 | 48,735 full SHA256; 2 large-file samples | 73,233 paths |
| AnyPod archive | 3,131 | 678,860,290,570 | 2,078 full SHA256; 2 large-file samples | 3,190 paths |

Each copy used an absent staging directory, numeric ownership, preserved modes/timestamps/hardlinks/xattrs, one-filesystem traversal, and refusal to overwrite existing files. Verification checked the complete namespace, file types, ownership, modes, hardlinks, symlinks, sizes, complete xattrs and every entry's nanosecond mtime. Large-file sampling is not a full hash of every media byte. All three nonempty AnyPod SQLite databases passed immutable read-only `PRAGMA integrity_check`; no WAL or rollback journal was present.

GNU `cp --reflink=always` initially rejected the cross-dataset clone ioctl with EXDEV. Inspection found only five empty directories remaining, not copied files; those were preserved in the private ledger before retrying into an absent destination. The previously demonstrated `--reflink=auto` path succeeded with observed block-clone savings: 2,990,080 bytes for AnyPod config/database, 31,454,199,808 for Plex, and 675,175,309,824 for the archive. Corresponding pool-allocation deltas were 45,056, 168,796,160 and 865,755,136 bytes. Ark continued scrubbing throughout; its final copy sync took several minutes, and cutover waited for the copy unit to become genuinely inactive with exit zero.

## Quarantine and mounts

The source GUIDs survived filesystem-specific `zfs rename -u` into these non-colliding archives outside Sanoid's configured roots:

| Source | Archive | Preserved GUID |
| --- | --- | --- |
| `ark/anypod` | `ark/legacy/consolidated-20260906-anypod` | `13068548920382062002` |
| `black-box/docker/anypod` | `black-box/legacy/consolidated-20260906-anypod` | `10201127423066540134` |
| `black-box/docker/plex` | `black-box/legacy/consolidated-20260906-plex` | `14660112101209533254` |

Each source was unmounted before rename, and its exposed mount stub was checked empty before placing any ordinary directory at that path. The empty retired OS stub `/mnt/ark/anypod` was removed with `rmdir`. Exactly three filesystems mount; all 65 quarantined datasets are read-only, legacy filesystems have `canmount=off` and `mountpoint=none`, and volumes have `volmode=none`. No volume device nodes remained. Nothing released legacy guaranteed writable-restore capacity.

A synthetic file in the unmounted agents directory made an actual ZFS mount fail with `directory is not empty`. After removing only that probe, the dataset mounted. A separate unmount of all three active filesystems found empty OS mount stubs, and restarting Debian's packaged `zfs-mount.service` restored exactly those three mounts. Distinct UIDs 62001 and 62002, supplementary GID 3000 and umask 002 cross-wrote, renamed and deleted probes under both `/mnt/ark/media` and `/mnt/ark/media/anypod`; setgid and group-write inheritance passed. Probes were removed.

Setting `xattr=sa` on empty agents produced the canonical local value `on` on OpenZFS 2.3.9. The declared `xattr=on` then produced no policy drift. Every active dataset retains local `fresh-v1` and `verified` markers.

## Sanoid and reconciliation

The revised guard physically rejected the still-present verified child datasets before cutover without executing Sanoid. After cutover, native reconciliation installed the nonrecursive two-root configuration and stricter guard. Real snapshot and prune services exited zero. No retention period was due, so that snapshot run correctly added nothing; this does not claim a fresh scheduled snapshot was created during the proof.

A uniquely marked held `frequently` snapshot was the only candidate in read-only prune output. Native Sanoid warned but exited zero; the actual wrapped prune service exited 1, and the Healthchecks API reported down. Releasing only that probe's GUID-checked hold allowed Sanoid to remove it, the service recovered to exit zero, and the API reported both Sanoid checks up. Every pre-existing and consolidation snapshot remained. The native timer resumed. The synthetic prune probe is the only snapshot deliberately removed during this consolidation.

The [full native rerun](reconcile-noop.txt) made no resource changes. The independent [read-only check](reconcile-check.txt) reported 74 unchanged resources, no changes or unknowns, and `3 active, 65 quarantined`. All 315 pytest tests and five Sanoid unittest tests passed; targeted Ruff passed. No failed systemd units or active application consumers remained. [Verification records](verification.json) contain the copy counters, identity preservation, mount/permission checks, SQLite results, Sanoid failure/recovery, API statuses and pool scan state. Full GUID inventories and operational scripts remain root-only under `/var/lib/pod042-storage-migration/consolidation-20260906`.

## Remaining boundaries

Both pools were ONLINE with zero known errors. Black-box retained its clean 06:05:33 PDT scrub result; this consolidation did not restart it. Ark kept original start `1788686258`, no new pause, and advanced to 8,444,473,868,288 issued bytes during final verification. It was still SCANNING, not finished, so its Healthchecks status remained honestly down/started from the earlier planned pause.

The first cold boot of this final three-mount layout remains an attended operation. Original data and snapshots in the same pools are rollback protection, not independent backup. Reservation release, application activation and per-stack authority, SMB/networking, and offsite backup/restore remain separate work.
