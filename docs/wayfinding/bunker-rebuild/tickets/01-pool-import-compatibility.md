---
status: closed
type: research
claimed: subagent
blocked-by: []
---

# Pool import compatibility

## Question

Will `capacity` (raidz1 + spare) and `performance` (NVMe mirror) import cleanly into a current Proxmox VE install, and what must the install/import procedure account for?

Specifics to pin against primary sources (OpenZFS docs, Proxmox docs, TrueNAS release notes):

- ZFS feature flags: current TrueNAS SCALE OpenZFS version vs the OpenZFS shipped in current Proxmox VE. Any TrueNAS-enabled feature the Proxmox kernel cannot read?
- Intel VMD: the NVMe mirror currently sits behind the VMD RAID controller (`0000:00:0e.0`). Does the Proxmox installer/kernel see VMD-attached NVMe? If VMD is disabled in BIOS, do the pool's device paths survive (pools use by-partuuid labels — confirm import is unaffected)?
- TrueNAS partitioning quirks: swap partitions on data disks, altroot `/mnt`, `zpool import -f` needs, hostid mismatch handling.
- System datasets: `performance/.system`, `ix-apps`, `ix-applications` — safe to destroy after import? Anything that pins the pool to TrueNAS middleware?
- Mountpoint strategy: pools mount at `/mnt/{capacity,performance}` today; keep or re-root under Proxmox conventions?

## Resolution

[`research/pool-import-compatibility.md`](../research/pool-import-compatibility.md) records the primary-source and live-host findings. Current Proxmox VE 9.2's OpenZFS 2.4 is compatible with the observed TrueNAS 24.10.2.4 pools; retain VMD initially, import without mounting to validate, keep `/mnt/{capacity,performance}`, then remove TrueNAS-only datasets only after their contents are deliberately retired or extracted.
