---
status: closed
claimed: subagent-zvol-migration
type: task
blocked-by: []
---

# Migrate VM storage off the SSD pool

## Question

Scope confirmed by Thurston 2026-07-24: **retain the OpenClaw VM image, moved to the `capacity` (spinning) pool** — it stays as reference material through the pod042 buildout, freeing `performance` SSD space for the new pod042 zvol. Migrate `performance/openclaw` (100G zvol) to `capacity` via zfs send/recv while the VM is stopped, repoint the VM's DISK device path, and update `truenas_vms.openclaw` in ansible/inventory/targets/group_vars/truenas.yml to match. [Sunset OpenClaw](08-sunset-openclaw.md) phase 2 will eventually delete it from `capacity` instead. [Playbook and VM provisioning design](07-playbook-and-vm-design.md) places pod042's zvol on `performance`.

### Migration log

On 2026-07-24, verified OpenClaw VM 12 was stopped with autostart disabled, snapshotted `performance/openclaw@migrate`, and replicated it through a detached local ZFS send/receive to `capacity/openclaw`. The received zvol retained its 100 GiB volsize and 16 KiB volblocksize; the middleware DISK path now points to `/dev/zvol/capacity/openclaw`. After verification, removed the source zvol and both migration snapshots. `performance` pool usage fell from 787,362,213,888 to 635,421,106,176 bytes, freeing 151,941,107,712 bytes (141.5 GiB) of SSD space.
