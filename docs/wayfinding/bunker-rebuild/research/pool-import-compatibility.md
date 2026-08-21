# Pool import compatibility

## Verdict

`capacity` and `performance` can be imported intact by current Proxmox VE. The source host runs TrueNAS SCALE 24.10.2.4 with OpenZFS 2.2.99-1; current Proxmox VE 9.2 ships ZFS 2.4, a newer OpenZFS release. The live pools have no active or enabled feature outside the source release's feature set, and that set is included in OpenZFS 2.4. Do not run `zpool upgrade` during the import; validate the actual target with a no-mount import first. Feature flags are one-way, so optimism is not a recovery plan. [TrueNAS 24.10 release notes](https://www.truenas.com/docs/scale/24.10/gettingstarted/scalereleasenotes/) · [Proxmox VE 9.2 release](https://proxmox.com/en/about/company-details/press-releases/proxmox-virtual-environment-9-2) · [OpenZFS feature flags](https://openzfs.github.io/openzfs-docs/Basic%20Concepts/Pool%20Structure/Feature%20Flags.html)

## Live-host evidence

Read-only inspection via `ssh truenas` on 2026-08-19 established the following.

| Item | Evidence |
| --- | --- |
| Source software | `/sbin/zfs version` reports `zfs-2.2.99-1` and `zfs-kmod-2.2.99-1`; `/etc/version` reports `24.10.2.4`. This matches the TrueNAS 24.10 component-version table. [TrueNAS release notes](https://www.truenas.com/docs/scale/24.10/gettingstarted/scalereleasenotes/) |
| Pool health and layout | `zpool status -P` reports `capacity` ONLINE as a four-member raidz1 plus spare, and `performance` ONLINE as a two-member mirror; both report no known data errors. |
| Active on-disk features | Both pools have the active features `empty_bpobj`, `lz4_compress`, `spacemap_histogram`, `enabled_txg`, `hole_birth`, `extensible_dataset`, `embedded_data`, `userobj_accounting`, `project_quota`, `spacemap_v2`, `log_spacemap`, `zilsaxattr`, `head_errlog`, and `vdev_zaps_v2`. `performance` additionally has active `block_cloning`. All other non-disabled flags are merely `enabled`, including `raidz_expansion`, `fast_dedup`, `blake3`, `redaction_list_spill`, and `zstd_compress`. |
| Compatibility setting | Both pools report `compatibility=off`. That allows any feature source OpenZFS supports, so the observed feature-state check is required rather than implied by policy. [OpenZFS pool properties](https://openzfs.github.io/openzfs-docs/man/v2.4/7/zpoolprops.7.html) |
| Current paths | Both pools are currently mounted through the TrueNAS alternate root `/mnt`. `zfs get mountpoint` reports the effective paths `/mnt/capacity` and `/mnt/performance`. |
| VMD hardware | `0000:00:0e.0` is Intel `8086:467f`, using the `vmd` driver. The two Samsung 970 EVO Plus controllers are visible behind it and use the regular `nvme` driver. |

The OpenZFS feature model requires support only for **active** on-disk changes to import read-write; an `enabled` flag has not necessarily changed the on-disk format. OpenZFS 2.4's feature reference includes the observed feature names, including `block_cloning`, `raidz_expansion`, and the other 2.2-era flags. This makes the current source/destination combination compatible on evidence, not merely on pool version numbers. [OpenZFS 2.4 feature reference](https://openzfs.github.io/openzfs-docs/man/v2.4/7/zpool-features.7.html) · [feature-state semantics](https://openzfs.github.io/openzfs-docs/Basic%20Concepts/Pool%20Structure/Feature%20Flags.html)

## Intel VMD

Leave VMD **enabled** for the first Proxmox boot. It already works with the live Linux host, and current Proxmox VE 9.2 uses Linux 7.0. The upstream Linux `vmd` driver explicitly supports this controller ID (`0x467f`) and enumerates the child PCI bus, so the installer/kernel has the necessary driver. [Proxmox VE 9.2 release](https://proxmox.com/en/about/company-details/press-releases/proxmox-virtual-environment-9-2) · [Linux VMD driver](https://github.com/torvalds/linux/blob/master/drivers/pci/controller/vmd.c)

Disabling VMD should not change the mirror's ZFS identity, but it is an unnecessary hardware-variable during first import. The pool members are ordinary GPT partitions, not an Intel RAID volume:

| `performance` vdev label | Current device | SSD serial |
| --- | --- | --- |
| `/dev/disk/by-partuuid/3c3e9dab-5619-43c0-954f-37eaa9b273f6` | `/dev/nvme1n1p2` | `S59ANM0W427759V` |
| `/dev/disk/by-partuuid/14022010-938a-40f8-8cd8-758515185b18` | `/dev/nvme0n1p2` | `S6S1NS0T644144F` |

`zpool status -P performance`, `/dev/disk/by-partuuid`, and `udevadm info` all agreed on that mapping. VMD owns and hides the child PCIe paths while enabled; with it disabled the kernel may assign different `nvmeN` names, but the on-disk GPT PARTUUIDs and ZFS labels do not change. On Linux, `zpool import` discovers pools with `libblkid` unless given a cache or search path, rather than depending on a particular `/dev/nvmeN` name. [Linux VMD driver](https://github.com/torvalds/linux/blob/master/drivers/pci/controller/vmd.c) · [OpenZFS import](https://openzfs.github.io/openzfs-docs/man/v2.4/8/zpool-import.8.html)

So disabling VMD is not expected to break import **provided both native NVMe devices appear**. It remains an untested firmware change: boot the installer or a live system, confirm both PARTUUID symlinks resolve, then use the no-mount import validation below. Do not create an Intel/VROC array or let the installer repartition either NVMe.

## TrueNAS layout and import behavior

Every data-pool disk has a 2 GiB first GPT partition with the Linux-swap type GUID `0657fd6d-a4ab-43c4-84e5-0933c84b4f4f`, followed by the ZFS member partition. This includes all five capacity disks (four raidz members plus the spare) and both NVMe disks. `/proc/swaps` is empty on the live host. These partitions are harmless remnants/auxiliary partitions; preserve them, but install Proxmox only on the separate Samsung 870 EVO boot disk (`/dev/sda` today). The data vdevs are the `p2` partitions.

`/mnt` is an **alternate root**, not a durable pool setting. OpenZFS prepends `altroot` only while the system is up, and setting it normally uses `cachefile=none`. A normal Proxmox import will not inherit the TrueNAS `/mnt` alternate root. [OpenZFS pool properties](https://openzfs.github.io/openzfs-docs/man/v2.4/7/zpoolprops.7.html)

The safe import sequence is:

1. Before shutdown, record `zpool status -P`, `zpool get all`, and `zfs get -r mountpoint`; then stop consumers and run `zpool export capacity` and `zpool export performance`. A clean export avoids the "potentially active" protection.
2. Install Proxmox only to the boot SSD. Confirm all expected `p2` partitions are present and no installer action touched them.
3. On the new host, run `zpool import` to inspect discovery, then `zpool import -N capacity` and `zpool import -N performance`. Check `zpool status -x`, `zpool get all`, and the absence of `unsupported@…` properties before mounting. `-N` deliberately imports without mounting filesystems. [OpenZFS import](https://openzfs.github.io/openzfs-docs/man/v2.4/8/zpool-import.8.html)
4. If the old system was not cleanly exported, and only after it is powered off and the device list is verified, retry the affected import with `-f`. `-f` is for a pool that appears potentially active; it is not a repair operation. Do not use `-F`, `-X`, or recovery flags for a healthy pool, because they can discard transactions. [OpenZFS import](https://openzfs.github.io/openzfs-docs/man/v2.4/8/zpool-import.8.html)

No hostid needs copying. The hostid is relevant to OpenZFS's optional multihost protection, not to the pool's portable identity; the clean export above is the correct way to avoid the active-host safeguard. If an unclean move requires `-f`, it is a one-time assertion that the old host cannot be using the pool, not a reason to clone TrueNAS identity. [OpenZFS pool properties](https://openzfs.github.io/openzfs-docs/man/v2.4/7/zpoolprops.7.html)

## Dataset disposal

None of these datasets pins the pool format to TrueNAS; they are ordinary ZFS datasets. They are safe to destroy only after their contents are either intentionally retired or copied to the replacement service.

- `performance/.system` is the TrueNAS system dataset (11.9 GiB live). It contains debugging/core material, encryption keys, and TrueNAS Samba metadata. It is safe to remove after the final check for any needed keys and after accepting loss of TrueNAS-specific Samba/system history; the new Proxmox services must create their own state. [TrueNAS system-dataset documentation](https://www.truenas.com/docs/scale/24.10/scaleuireference/systemsettings/advancedsettingsscreen/)
- `performance/ix-apps` is the hidden 24.10 Docker dataset (91.9 GiB live), storing Docker configuration, catalog data, and app metadata. It is TrueNAS-managed and should not be repurposed. It can be destroyed only after extracting every application state to keep. In particular, inspect its Plex app-mount data before removal; ticket 06 owns the migration decision. [TrueNAS App Storage](https://apps.truenas.com/getting-started/app-storage/)
- `performance/ix-applications` is the retained pre-24.10 Kubernetes dataset (11.0 GiB live). TrueNAS documents that 24.10 does not use it after migration and that it can be removed once migration is complete, at the cost of no longer being able to revert to 24.04. On this project, it is removable after any required Home Assistant/Plex/Storj extraction and after accepting the permanent retirement of TrueNAS. [TrueNAS App Storage](https://apps.truenas.com/getting-started/app-storage/)

Destroy the three roots only after their dependency snapshots/clones have been reviewed. The live trees contain many snapshots and app datasets, so `zfs destroy -r` is intentionally destructive rather than housekeeping.

## Mountpoint decision

Keep `/mnt/capacity` and `/mnt/performance` as the Proxmox host paths. They are already the paths embedded in the surviving service data and the desired replacement uses host-mounted storage. After the non-mounting import, set the two root datasets explicitly to those paths before mounting:

```sh
zfs set mountpoint=/mnt/capacity capacity
zfs set mountpoint=/mnt/performance performance
zfs mount -a
```

The current child datasets mostly have default/inherited mountpoints, so they will follow their roots. Remove or explicitly deal with the TrueNAS-only `legacy` mountpoints before relying on `zfs mount -a`.

This does not conflict with Proxmox storage configuration. Proxmox's `zfspool` backend allocates within a specified pool or dataset, and its `mountpoint` option does **not** change ZFS's dataset mountpoint property. If later tickets allocate VM/LXC disks here, create a dedicated child dataset and point `pvesm` at it; do not hand the service-data roots to the VM-storage backend. [Proxmox ZFS storage](https://pve.proxmox.com/wiki/Storage:_ZFS)
