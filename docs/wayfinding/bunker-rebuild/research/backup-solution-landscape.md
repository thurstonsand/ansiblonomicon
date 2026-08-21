# Offsite backup solution landscape

This surveys an offsite copy of the irreplaceable subset, not a replacement for ZFS snapshots or a plan to retire Storj. The candidate data is likely below 2 TB today; `capacity/backup` is 1.15 TB, but retained backup history and encrypted/deduplicated repository overhead mean the eventual allocation must be measured before purchase.

## Evaluation frame

The new host has native ZFS. A ZFS snapshot is an atomic, consistent image of a dataset; `zfs snapshot -r` creates a hierarchy at the same time. That makes a named snapshot the right source boundary for a file backup, regardless of backup program. Database/application consistency still needs application quiescing or a pre-snapshot dump. [OpenZFS snapshot documentation](https://openzfs.github.io/openzfs-docs/man/master/8/zfs-snapshot.8.html)

For unattended operation, every candidate needs a declared timer/job, a non-zero exit routed to the host's notification path, a freshness check (latest successful snapshot), and a periodic integrity check plus restore drill. A completed backup process is not evidence that the selected data is restorable. These are integration responsibilities for the CLI tools; PBS supplies more of them itself.

## Storage pricing

Monthly figures are published on 2026-08-19, before tax, and represent allocated provider storage rather than a forecast of compressed/deduplicated backup size. They exclude one-time seed/restore transfer, local disks, and any provider fees called out below.

| Target | 1 TB | 2 TB | 5 TB | Pricing boundary |
| --- | ---: | ---: | ---: | --- |
| [Backblaze B2](https://www.backblaze.com/cloud-storage/pricing) | $6.95 | $13.90 | $34.75 | Pay-as-you-go object storage. First 10 GB and egress up to 3× average stored capacity are free; further egress is $0.01/GB. No minimum storage-duration fee. |
| [Wasabi Hot Cloud Storage](https://wasabi.com/pricing) | $7.99 | $15.98 | $39.95 | Pay-as-you-go object storage; no egress or API-request charge. Objects deleted within the default 90-day minimum are charged for the remaining days. [Policy](https://docs.wasabi.com/docs/how-does-wasabis-minimum-storage-duration-policy-work) |
| [Hetzner Storage Box](https://www.hetzner.com/storage/storage-box/) | €3.20 | €10.90 | €10.90 | BX11 is 1 TB at €3.20/month; 2 TB requires the 5 TB BX21 at €10.90/month, which also covers 5 TB. These net EUR prices come from Hetzner's public [BX11](https://website-price-api.hetzner.com/api/v1/products/ROBOT_1333) and [BX21](https://website-price-api.hetzner.com/api/v1/products/ROBOT_1334) pricing endpoints. Storage Box is SSH/file storage, not S3 object storage. |
| [rsync.net ZFS send account](https://www.rsync.net/products/zfs.html) | $125 | $125 | $125 | Native ZFS send/receive requires its stated 10 TB minimum at $0.0125/GB-month: $125/month using the provider's decimal units. Transfer is included. It is not priced at the small-data tiers. |
| [zfs.rent](https://zfs.rent/pricing) | $20* | $20* | $20* | One physical-drive slot is $240 for 12 months, effectively $20/month, irrespective of drive capacity. The customer buys, ships, and retains the drive; redundancy is the customer's responsibility. The first 1 TB/month of transfer is free and extra transfer is $5/TB. |
| Friend's ZFS host | no provider price | no provider price | no provider price | The subscription cost may be zero, but the actual cost is remote hardware, power, capacity, connectivity, and an explicit agreement about maintenance and recovery access. |
| Proxmox Backup Server (PBS) | no intrinsic storage price | no intrinsic storage price | no intrinsic storage price | PBS is backup software, not offsite capacity. Price the remote PBS datastore or its supported S3 storage separately; it cannot supply an offsite copy by itself. |

\* zfs.rent requires an annual commitment and excludes the drive, shipping, and any transfer overage. It is a physical-colocation service, not a conventional cloud-storage bill.

## ZFS-native replication

`zfs send` serializes a snapshot and `zfs receive` recreates it; incremental streams move only the changed blocks. It can replicate a hierarchy with `-R`. [OpenZFS send and receive](https://openzfs.github.io/openzfs-docs/Basic%20Concepts/Operations/Send%20and%20Receive.html) Sanoid manages snapshot policies, while Syncoid performs asynchronous incremental push replication over SSH, supports recursive replication and enables resumable streams where available. Sanoid also has `--monitor-snapshots` and `--monitor-health` modes intended for Nagios-style monitoring. [Sanoid/Syncoid README](https://github.com/jimsalterjrs/sanoid/blob/master/README.md)

This is the only surveyed path that preserves the ZFS dataset/snapshot structure directly. Restoring a whole dataset is correspondingly direct: receive the selected remote snapshot/stream into a new local dataset; individual files can be read from a mounted snapshot. The price is operational: snapshots, Syncoid scheduling, replication-age monitoring, alert delivery, target retention, and target access all remain host configuration.

### rsync.net

rsync.net provides ZFS send/receive over SSH on a special account. The customer controls the remote pool and snapshots; rsync.net says the account has a 10 TB minimum and includes support and transfer. [rsync.net ZFS service](https://www.rsync.net/products/zfs.html) This is the most managed commercial native-ZFS target in the survey, but its $125/month minimum buys far more capacity than the stated requirement. Its own service snapshots are an additional recovery layer, not a substitute for monitoring the source-to-target replication age.

### zfs.rent

zfs.rent provides a dedicated VM with the customer's physical drive passed through. It advertises a flat $20/slot-month, pre-loading the drive before shipping, and explicitly leaves redundancy to the customer. [zfs.rent overview](https://zfs.rent/) Its low capacity-independent recurring rate is misleading if treated as ordinary object storage: it requires purchasing and shipping a drive, remote ZFS administration, an annual commitment, and either accepting one remote drive or paying for multiple slots and a mirror/RAIDZ. This has more moving parts than the target problem warrants unless physical-drive ownership is the goal.

### A friend's ZFS box

Syncoid is equally applicable to a trusted friend's ZFS host. It avoids a storage-provider bill and remains a normal ZFS restore, but turns the backup target into shared infrastructure. It needs a constrained receive account, mutually understood space/retention limits, monitoring from the Bunker, and a recovery arrangement that survives either party's outage. This is operationally simpler than operating a cloud VM, but less independent than a commercial provider.

## File backup to object or remote file storage

All three tools support encrypted, deduplicated historical file snapshots and restore files rather than ZFS streams. They do not replace local ZFS snapshots; schedule a ZFS snapshot, expose or mount that immutable view, back up that view, then retain/destroy it according to the ZFS policy. This avoids a long file walk observing live changes.

### Restic

Restic supports direct B2 repositories and S3-compatible repositories, so B2 and Wasabi are straightforward backends. Its documentation specifically recommends B2's S3-compatible API, and documents both the native B2 and generic S3 backends. [Restic repository backends](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html) On Linux it has no native ZFS snapshot switch—the documented automatic filesystem snapshot option is Windows VSS—so the ZFS snapshot/mount boundary is an explicit host job.

Restic is a command, not a backup daemon; its documentation calls for external scheduling such as systemd or cron and advises regular `restic check`. Backup errors return non-zero, so a systemd service plus the host notification path can make failure visible. [Restic backup, checking, scheduling, and exit behavior](https://restic.readthedocs.io/en/stable/040_backup.html) Restore is clear for both drills and incidents: browse a repository with FUSE or restore a selected snapshot/path to a target directory. [Restic restore](https://restic.readthedocs.io/en/stable/050_restore.html)

B2 is cheaper and has a useful 3×-stored-capacity free egress allowance, but a disaster restore above that allowance costs $0.01/GB. Wasabi makes egress/API cost predictable but its 90-day deletion charge makes frequent pruning/rewrite behavior less simple. The tool configuration is otherwise the same S3 shape.

### Borg with Hetzner Storage Box

Hetzner Storage Box directly supports Borg over its SSH service (port 23) and offers an append-only mode. The latter permits new archives while preventing permanent deletion by the restricted backup client; keep a separate unrestricted maintenance credential. [Hetzner SSH/Borg access](https://docs.hetzner.com/storage/storage-box/access/access-ssh-rsync-borg) This is a conventional remote filesystem target rather than object storage and includes Storage Box snapshots as a provider-side recovery layer.

Borg's documented append-only mode protects committed segments from a compromised client, though normal retention/compaction needs deliberate maintenance access. [Borg append-only mode](https://borgbackup.readthedocs.io/en/stable/usage/notes.html) A timer and alert integration are still required. Borg can perform repository checks and full cryptographic data verification, and can extract selected paths with a dry run. [Borg check](https://borgbackup.readthedocs.io/en/stable/usage/check.html) [Borg extract](https://borgbackup.readthedocs.io/en/stable/usage/extract.html)

This is the lowest listed cost at the 1–5 TB range and uses mature, simple SSH credentials. Its tradeoff is that a backup job, ZFS snapshot wrapper, retention maintenance, integrity checking, and alerting are separate declarations; its restore vocabulary is Borg archives rather than native ZFS datasets.

### Kopia

Kopia supports B2 directly and S3-compatible repositories, and its policies cover scheduling and retention. [Kopia repositories](https://kopia.io/docs/repositories/) [Kopia features](https://kopia.io/docs/features/) Unlike Restic and Borg, it documents actions explicitly for ZFS: a before action creates and mounts a ZFS snapshot and redirects the backup to it; an after action unmounts and destroys it. Actions are opt-in, and essential actions fail the snapshot by default. [Kopia ZFS actions](https://kopia.io/docs/advanced/actions/)

Kopia has a GUI as well as CLI, supports mounting, full restore, or selected-file restore, and can verify stored snapshots, including downloading a random percentage of files. [Kopia restore options](https://kopia.io/docs/faqs) [Kopia verification](https://kopia.io/docs/reference/command-line/common/snapshot-verify/) The integrated ZFS action is attractive, but it adds action scripts and an enabled action execution surface. It should be assessed against the smaller, explicit systemd-plus-Restic/Borg shape rather than assumed to be simpler.

## Proxmox Backup Server: useful, but bounded

PVE's integrated `vzdump` backup workflow creates consistent snapshots of KVM guests and containers, retains their configuration, and schedules guest backup jobs. PBS adds deduplication, encryption, file restore, and offsite PBS synchronization/S3 capability to that workflow. [PVE backup and restore](https://pve.proxmox.com/pve-docs/pve-admin-guide.html#chapter_vzdump)

PBS can also back up arbitrary host paths, but only through an explicitly configured `proxmox-backup-client` invocation, for example `root.pxar:/` or `disk1.pxar:/mnt/disk1`. This is a file/archive backup, not automatic capture of every ZFS dataset just because PVE can back up guests. It needs its own selection/exclusions, timer, and preferably a source ZFS snapshot boundary. [PBS backup client](https://pbs.proxmox.com/docs/backup-client.html)

A PBS remote is another PBS installation/datastore; its sync jobs can be scheduled and restricted to verified or encrypted backups. [PBS remotes and sync](https://pbs.proxmox.com/docs/managing-remotes.html) PBS has the strongest built-in failure visibility surveyed: scheduled verification, GC, and synchronization generate notifications, with SMTP, Gotify, and webhook targets and error severities. [PBS maintenance notifications](https://pbs.proxmox.com/docs/maintenance.html) [PBS notification events](https://pbs.proxmox.com/docs/notifications.html)

PBS is a good companion if the rebuilt host has guests whose lifecycle belongs in the PVE UI. It is not a self-contained answer for the Bunker's arbitrary `capacity`/`performance` datasets or its offsite storage bill, and deploying/operating a remote PBS solely for under 2 TB of files may defeat the simplicity goal.

## Shortlist for the follow-up decision

These are candidates for the grilling ticket, not a recommendation or a final choice.

1. **Restic on ZFS snapshots to Backblaze B2.** Lowest-complexity object-store route: one mature CLI, inexpensive elastic capacity, direct B2 support, documented checks, and simple file restore. Tradeoffs: declare the ZFS snapshot wrapper, timer, retention, freshness/error alert, and restore drill; account for B2 restore egress after the 3× allowance.
2. **Borg on ZFS snapshots to a Hetzner Storage Box.** Smallest published 1–5 TB storage bill, SSH rather than S3 credentials, Borg append-only protection, and straightforward selective extraction. Tradeoffs: not native ZFS, 2 TB means buying the 5 TB tier, and the same host-side scheduling/monitoring/maintenance work remains.
3. **Sanoid/Syncoid to an independently administered friend's ZFS host.** Preserves ZFS directly and makes a full-pool/dataset recovery mechanically clean without a cloud-storage account. Tradeoffs: it shifts the administration, availability, capacity, and recovery-access burden into a human relationship; it needs explicit lag monitoring and alerting. Commercial native targets are available, but rsync.net's 10 TB minimum and zfs.rent's physical-drive operations make them poor small-subset fits.

PBS should be considered separately as the PVE guest-backup layer if guests need it. It does not displace one of these as the offsite backup plan for arbitrary NAS datasets without adding a PBS datastore/storage design.
