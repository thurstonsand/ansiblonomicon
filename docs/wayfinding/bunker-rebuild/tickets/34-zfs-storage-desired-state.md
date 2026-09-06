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

Round 1 keeps the protection layer simple. Both pools use `failmode=wait`; only the `black-box` NVMe mirror enables `autotrim`. Debian's packaged monthly scrub timer runs for both pools on its standard schedule. SMART monitors the five HDDs, two pool NVMes, and boot SSD through stable identities, with daily short tests and monthly long tests staggered across devices. Ark's hot spare always requires operator activation after an alert; no custom replacement code or `autoreplace` fiction enters the host. Sanoid waits for the fresh dataset layout rather than recursively retaining the TrueNAS-era tree. External failure delivery gates scheduled maintenance, so the minimal pod042 identity and alert path comes first.
