# Fresh datasets and legacy quarantine

`layout.toml` declares the six active filesystems. The native capability owns the `media` group and ACL package; its final hook converges ZFS properties through the GUID-guarded helper because mise has no dataset resource. `mise pod042 --check` also runs the helper's read-only check. Explicit mountpoints and local property values keep active children writable and mountable when their pool roots become unmounted, read-only legacy storage.

Every active filesystem must have a **local** `org.ansiblonomicon:layout=fresh-v1` marker and matching immutable creation properties. Normal reconciliation additionally requires a **local** `org.ansiblonomicon:migration=verified` marker. It refuses to adopt existing TrueNAS filesystems, ignores no unknown children, and never deletes datasets or snapshots. Service directory ownership stays with the copied numeric identities until each stack declares its image-specific policy. Shared roots are `root:media` with mode `2775`.

## One-time migration

Do not run full reconciliation or activate Sanoid until migration verification finishes. Its runtime guard also refuses unverified snapshot targets. This operation assumes no application consumers are running.

1. Check pool GUIDs against `pod042_storage.POOLS`, record dataset names/GUIDs/properties, all snapshot GUIDs, and `usedby*` counters under root-only `/var/lib/pod042-storage-migration`. Take and hold a migration snapshot on each pool separately. Preserve all earlier snapshots, including pre-Debian and pre-feature-upgrade snapshots.
2. Apply only the native `datasets` accounts, packages and files steps, without its final hook. Create `black-box/legacy` with `mountpoint=none`, `canmount=off` and `readonly=on`. Rename the old `black-box/docker` into `black-box/legacy/docker`, then give that source the private temporary mountpoint `/mnt/.pod042-migration/docker`, `canmount=noauto` and `readonly=on`. Mount it explicitly. Make `ark/watch` and `black-box/apps/plex` read-only too.
3. From this directory run `sudo -n /usr/bin/python3 reconcile.py prepare`. Only this explicit mode creates filesystems; it marks them pending and does not quarantine the source tree. It refuses occupied destination mountpoints. Parent datasets are prepared before their children.
4. Run `sudo -n /usr/bin/python3 migrate.py copy GROUP`, serially for `docker`, `plex`, `anypod-db`, `media`, and `anypod`. Each operation checks mounts and readonly sources, scans unsupported xattrs and unique apparent size, and requires room for an ordinary-copy fallback plus 1 TiB on ark or 16 GiB on black-box. It uses native GNU cp with strict metadata preservation, one-filesystem traversal and `--reflink=auto`; no existing file may be overwritten. It reports cloned-block savings and physical pool-allocation changes before normalizing permissions and verifying the copy.
5. Confirm all five groups passed. Check the AnyPod SQLite database read-only. Only then mark `black-box/docker/anypod` verified: both the `docker` and `anypod-db` groups contribute to it. Mark the other copied datasets verified after their corresponding checks, and verify `black-box/agents` is empty before marking it verified.
6. Rename all old child datasets under their pool's `legacy` parent. Preserve root filesystem contents in place. Unmount the fresh children, then legacy children, then the pool roots, deepest mountpoints first, without force. Run `reconcile.py apply`; it makes roots and every legacy filesystem read-only, unmountable and `mountpoint=none`, makes legacy volumes read-only with `volmode=none`, and remounts only declared active filesystems. Existing volume device nodes may linger until reboot; check them rather than assuming immediate removal.
7. Compare snapshot GUID inventories across renames, test shared writes under distinct numeric UIDs with supplementary GID 3000 and umask 002, and run the full guarded reconciliation and read-only check. Sanoid then covers only the new black-box workload trees.

`copy` is deliberately one-shot. On interruption, preserve the sources and inspect the pending destination. A repeat refuses existing files instead of assuming that a partial file is complete. Reset only a positively identified, still-pending destination after reviewing any child dataset contributions, then prepare and copy it again. Never reset a verified dataset. `migrate.py verify GROUP` is read-only but requires the migration source mounts to remain available; restore those read-only mounts explicitly for a later comparison.

## Accounting

| Source | Destination or disposition |
| --- | --- |
| `ark/watch/media/{movies,podcasts,tv}` and `downloads` | One `ark/media` filesystem; one cp invocation preserves download/library hardlinks |
| `ark/watch/anypod`, except `data/db` | `ark/anypod`, preserving its internal tree |
| `ark/watch/anypod/data/db` | `black-box/docker/anypod/db`; the bulk copy has no second writable database |
| Old `black-box/docker` | Fresh `black-box/docker`, preserving dormant configs without activating services |
| `black-box/apps/plex` | `black-box/docker/plex`, retaining `config/` placement |
| ark root's Frigate recordings, Ollama data and installer ISO | Preserved in the unmounted, read-only pool root; surveillance recordings are not public media |
| Watch Ghost/MySQL data, trash, recycle, copy, transcode and smb | Preserved under `ark/legacy/watch`; application merge decisions remain separate |
| Storj, old home/app/runtime datasets and guest zvols | Preserved under the appropriate `legacy` parent, with all snapshots and reservations |

There is no destruction phase here. Legacy retention is intentional until consumer migration and restore checks settle the remaining data. Same-pool snapshots and cloned files are rollback protection, not an independent backup. Pre-feature-upgrade snapshots do not reverse pool feature activation; their eventual removal requires a separate retention decision.

## Verification scope

The verifier checks the complete mapped namespace, file types, numeric ownership, normalized or preserved modes, non-ACL xattrs, symlink targets, hardlink equivalence, and regular-file sizes and nanosecond mtimes. It hashes all small files and databases, including WAL/SHM sidecars. For other large files it samples approximately 1/256 of paths at beginning, middle and end. It does **not** hash every media byte; most large files receive metadata verification, backed by observed block cloning and ZFS checksums. A scrub checks block integrity, not namespace equivalence.

Physical commissioning proved cross-dataset cloning with an 180.9 MB podcast copied and fully hashed, and a 31.09 GB movie copied in 0.35 seconds with 31.06 GB of additional cloned-block savings and three byte comparisons. Both used independently created POSIX filesystems; the temporary destinations were removed under GUID guards. A separate physical fixture proved omitted database paths, cross-operand hardlinks, xattrs, symlinks and group permissions, and detected same-size/same-mtime corruption, unexpected files and broken hardlinks. These probes do not stand in for the full migration's own verification.
