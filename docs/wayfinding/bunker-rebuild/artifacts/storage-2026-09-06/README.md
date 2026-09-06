# Physical storage completion, 2026-09-06

Verified on Debian 13 pod042 at deployed revision `42cbcca`, after the operator authorized direct physical implementation. No retired Ansible playbook ran, no application consumer was activated, and no original dataset or snapshot was destroyed.

This records the initial six-dataset commissioning. The operator subsequently approved consolidating to three active datasets; the current declaration and guarded procedure are in the [dataset README](../../../../../bootstrap/targets/pod042/datasets/README.md). [Consolidation verification](../consolidation-2026-09-06/README.md) records the completed three-dataset cutover separately rather than rewriting this historical evidence.

## Preservation and fresh layout

All five production copy groups completed before quarantine. Counts below describe unique regular files in each copy group.

| Group           |   Files |      Logical bytes | Content verification                       |
| --------------- | ------: | -----------------: | ------------------------------------------ |
| Docker          |  56,042 |     26,525,572,881 | 55,997 full hashes, 1 large-file sample    |
| Plex            |  48,896 |     38,859,691,627 | 48,735 full hashes, 1 large-file sample    |
| AnyPod database |       4 |          9,846,784 | 4 full hashes                              |
| Media           | 133,113 | 11,555,718,940,481 | 121,004 full hashes, 48 large-file samples |
| AnyPod archive  |   3,131 |    678,860,290,570 | 1,847 full hashes, 4 large-file samples    |

The verifier also checked namespace, required metadata and hardlink relationships. The media verification traversal counted 133,208 paths and 12,011,678,147,065 logical bytes when including hardlinks. Large-file sampling is not a full hash of every large file. Cross-dataset block cloning was demonstrated with synthetic data, a real podcast and a 31 GB movie before production copying. All three nonempty AnyPod SQLite files passed immutable read-only `PRAGMA integrity_check`; no WAL or rollback journal was present.

[`quarantine-verification.json`](quarantine-verification.json) records all 60 original dataset GUIDs and 3,758 original snapshot GUIDs retained across archival renames. Pool-root contents remain in place. Legacy children live below `ark/legacy` and `black-box/legacy`. All 62 quarantined datasets, including roots and new legacy parents, are read-only; legacy filesystems are unmounted with `mountpoint=none`, and volumes use `volmode=none`. No `/dev/zvol` entries remained. Every original volume's GUID, size and refreservation remained unchanged. Roughly 266 GB of black-box's guaranteed writable-restore capacity remains reserved, not reclaimed.

Only six fresh filesystems mount: `ark/media`, `ark/anypod`, `black-box/docker`, `black-box/docker/anypod`, `black-box/docker/plex`, and `black-box/agents`. Each has local `fresh-v1` and `verified` markers. OpenZFS 2.3.9 reports SA xattrs as `on`; declaring the canonical value removed a repeated equivalent property write.

[`mount-permission-verification.json`](mount-permission-verification.json) records an actual `overlay=off` mount refusal with a synthetic file in the unmounted agents directory, successful cleanup/remount, and a deepest-first unmount followed by the packaged `zfs-mount.service` restoring exactly those six filesystems. Distinct unprivileged UIDs 62001 and 62002, with supplementary media GID 3000 and umask 002, cross-wrote, renamed and deleted probe files on both ark roots. All probes were removed.

The first quarantine attempt stopped when `zfs rename -u` rejected a volume. A separate recovery checked the partially completed names against recorded GUIDs, used filesystem-specific rename flags, completed policy application and reverified every identity. It did not replay the one-shot script over partial state.

## Maintenance and alerting

All eight real SMART short tests passed earlier in commissioning. SMART health monitoring, staggered daily short/monthly long tests, ZED fault reporting, and Debian monthly scrub timers are enabled. ZED may automatically activate ark's registered spare; `autoreplace=off` does not disable that behavior.

Sanoid created exactly 12 hourly/daily/monthly snapshots across the four approved black-box filesystems. [`sanoid-snapshot-verification.json`](sanoid-snapshot-verification.json) rechecks all 3,758 original snapshot GUIDs after real snapshot and prune runs. No new Sanoid snapshot appeared in legacy or ark datasets.

A held, uniquely marked synthetic `frequently` snapshot demonstrated Sanoid's native exit-zero failure. Once its real creation time was old enough for the zero-retention policy, read-only pruning proposed only that probe. Native pruning warned and returned zero; the deployed adapter made the actual prune service fail with exit 1, and the Healthchecks API independently reported down. Releasing only the probe's hold let native pruning remove it; the service and external check recovered, and the native timer resumed. See [`prune-proof.json`](prune-proof.json) and [`healthchecks-status.json`](healthchecks-status.json). The earlier inaccessible-notification fixture preserved producer exit 42.

Black-box's post-migration scrub finished at 06:05:33 PDT in 5 minutes 41 seconds with zero repairs/errors. Ark resumed its original start `1788686258` and preserved its issued-byte bookmark. At 06:20 PDT it was 11.74% complete with zero repairs and no known data errors, not finished. Its Healthchecks check remains down from the planned pause and marked started until the actual scan succeeds. Do not send an artificial success ping. Both pools remain ONLINE; `longname` and `large_microzap` are enabled but not yet active. See [`pools-and-units.txt`](pools-and-units.txt).

## Reconciliation and review

The physical full rerun made no resource changes: [`reconcile-noop.txt`](reconcile-noop.txt). The independent read-only plan reported 0 create, 0 update, 74 unchanged, 0 remove, 0 unknown, followed by 6 active and 62 quarantined datasets: [`reconcile-check.txt`](reconcile-check.txt). No systemd units remained failed. The full 310-test pytest suite and five Sanoid tests passed. The commit hook reported no type errors and only the existing `pdfplumber` and `frontmatter` import warnings.

[Fable's final review](fable-review.md) found no critical closure gaps. Earlier reviews covered the secret boundary, monitoring corrections, copy/quarantine guards and preservation policy. Commits used the authorized unsigned fallback after 1Password signing failed.

## Explicit follow-up

- Confirm ark reaches a clean FINISHED scan with an end time after the preserved start; its normal completion hook must recover Healthchecks.
- Perform the first cold boot of the final mount layout while SSH credential unlock is attended. Initial Debian cache-import persistence passed before this layout; this round tested the real mount service without rebooting. Sleep settings and independent KVM were left alone.
- Retain legacy reservations unless the operator explicitly authorizes releasing guaranteed writable-restore capacity.
- Continue SMB, host networking, container runtime, per-stack identity/data authority and activation, and backup/restore work through tickets 35 through 39. Ghost/MySQL authority, Frigate placement, guest extraction, and Work/Orb commissioning are not proven by copying their data.

The detailed copy inventories, held migration tag, before-properties, dataset/snapshot GUID lists and operational journals remain root-only under `/var/lib/pod042-storage-migration` on pod042. No ping URL, API credential, application content or full file-hash inventory is copied here.
