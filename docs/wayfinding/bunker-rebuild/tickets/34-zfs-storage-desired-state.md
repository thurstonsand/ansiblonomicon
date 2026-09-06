---
status: open
type: grilling
blocked-by: [31]
---

# ZFS storage desired state

## Question

Reconfirm and specify the native mise declaration for imported `ark` and `black-box`: package ownership, import behavior, pool and dataset properties, fresh dataset layout, POSIX identities and ACLs, sanoid snapshots, scrub schedules, SMART monitoring, zed and hot-spare behavior, legacy-path retirement, and destructive-operation gates.

Use the closed storage decisions as constraints, but audit the Ansible role and cutover assumptions for obsolete TrueNAS behavior. Close with verification against real ZFS in the VM rig; then create a separate implementation ticket.

## Cutover progress

The 2026-09-05 cutover implemented only the minimum prerequisite and import slice. Native mise enables Debian `contrib`, installs `linux-headers-amd64`, `zfs-dkms`, and `zfsutils-linux`, and enables the standard cache-import and mount units. Pool imports remain explicit operator actions.

Both exported pool GUIDs matched the pre-wipe record. Read-only `-N` imports through `/dev/disk/by-id` showed the expected online four-disk raidz1 plus spare and two-disk NVMe mirror, no known data errors, and the `pre-debian-20260905T050835Z` snapshots. The operator then imported GUID `8619294010601504858` as `ark` and GUID `131852107186480998` as `black-box`, set only the root mountpoints to `/mnt/ark` and `/mnt/black-box`, and mounted inheriting datasets. After reboot, both pools returned by the cache, all four ZFS units were enabled and active, and representative datasets remained mounted. See [`artifacts/cutover-2026-09-05/`](../artifacts/cutover-2026-09-05/).

This does not close the ticket. Pool and dataset properties, permissions and ACLs, sanoid, scrub, SMART, zed policy, retired TrueNAS datasets, and destructive-operation gates still need the requested design pass.

## Grill progress

Round 1 keeps the protection layer simple. Both pools use `failmode=wait`; only the `black-box` NVMe mirror enables `autotrim`. Debian's packaged monthly scrub timer runs for both pools on its standard schedule. SMART monitors the five HDDs, two pool NVMes, and boot SSD through stable identities, with daily short tests and monthly long tests staggered across devices. The initial manual-spare preference was superseded on 2026-09-06: the operator accepts Debian ZED automatically activating ark's registered spare. `autoreplace=off` does not disable the compiled retire agent, and no supported switch was found. The spare remains registered; no custom replacement code or pool membership change is needed. Sanoid waits for the fresh dataset layout rather than recursively retaining the TrueNAS-era tree. External failure delivery gates scheduled maintenance, so the minimal pod042 identity and alert path comes first.

## Protection rollout

Independent Hark delivery passed on physical pod042 at `4b605cd`, running from `/` with an empty environment. `bf82c49` deployed GUID-guarded pool properties and SMART/ZED fault monitoring. `4cf50cd` moved repository setup to native mise resources and installed official backports smartmontools 7.5, fixing NVMe self-test support; the physical rerun reported 45 unchanged resources.

`c253536` and `65f47ce` deployed heartbeat and scrub Healthchecks, Debian's monthly scrub timers, and staggered daily short/monthly long SMART tests. All eight drives completed real short self-tests without errors. A paused black-box scrub correctly reported failure; the restarted scrub finished cleanly in 5 minutes 51 seconds and its check recovered. An actual systemd fixture with inaccessible notification credentials preserved the producer's exit status 42. The runtime helper reads root-only scoped credentials directly because this host removes systemd's credential directory before `ExecStopPost`. Failed notification hooks cannot block or overwrite producer results. Fable reviewed the corrections.

The heartbeat is up. Ark's commissioned scrub has a three-day completion grace and is temporarily paused during the bulk copy, with its original start time and 2.81 TB of issued progress preserved. Resume and verify that bookmark before closing; do not report a scrub complete from a successful start command. The host and Healthchecks schedules use America/Los_Angeles. The unrelated `truenas-pon-monitor` and `truenas-mam-update` checks remain for their later service migrations.

The operator explicitly authorized feature upgrades. Matching OpenZFS 2.3.9 kernel/userspace, GUID checks, clean recent scrub records and an allowlist preceded enabling `longname` and `large_microzap` on both pools. Recursive pre-feature-upgrade snapshots remain preserved. They protect data, not reversal of feature activation; rescue/import environments must support the enabled features.

## Fresh dataset rollout

`9701999` declares fresh POSIX filesystems and Sanoid, with independent checks for snapshot and prune jobs. Ordinary reconciliation refuses pending migrations, and Sanoid's runtime guard refuses unverified trees. Source snapshots are held under `pre-dataset-migration-20260906T101855Z`; the preservation inventory records 3,758 snapshot GUIDs. The physical migration is in progress through the [guarded dataset procedure](../../../../bootstrap/targets/pod042/datasets/README.md). Dormant application data is preservation, not approval to launch its services.
