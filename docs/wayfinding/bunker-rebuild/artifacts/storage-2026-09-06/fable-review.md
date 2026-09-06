# pod042 completion review (read-only)

Scope: delta 733b051..42cbcca and closure readiness of ticket 34 (`docs/wayfinding/bunker-rebuild/tickets/34-zfs-storage-desired-state.md`). HEAD verified as 42cbcca.

## Delta 733b051..42cbcca

Single change: `layout.toml` `xattr = "sa"` → `"on"`, README sentence explaining it. Correct. OpenZFS 2.3.0 made `sa` the default and an alias of `on`; `zfs get` reports `on` for either, so declaring `sa` would drift on every converge. The README pins the reasoning to 2.3.9, which matters because on pre-2.3 ZFS `on` means directory xattrs. This layout is host-specific, so no adapter is warranted.

## Ticket 34: ready to close, with pendings recorded

Every item in the ticket's question is now specified and proven on the physical host, which exceeds the ticket's own "verify in the VM rig" bar:

- package ownership, import, cache/mount units: closed at the 2026-09-05 cutover
- pool properties, feature upgrades with guards and pre-upgrade snapshots: closed
- fresh dataset layout: six filesystems, local fresh-v1 + verified markers, `--check` 74 unchanged / 0 create / 0 update, 6 active / 62 quarantined
- POSIX identities and ACLs: media gid 3000, posix acltype, distinct UID 62001/62002 cross-write/rename/unlink proof on both ark roots
- sanoid: deployed, 12 real snapshots across the 4 approved filesystems, held synthetic-old-snapshot proved native exit 0 vs wrapper exit 1 + HC down, prune touched only its own probe
- scrub schedule and monitoring: black-box post-migration scrub clean; ark scan resumed from the preserved start with bookmark
- SMART, ZED, spare: closed earlier in the ticket
- legacy retirement: 60 dataset GUIDs and 3,758 snapshot GUIDs retained, zvols readonly/volmode=none with volsize and refreservation unchanged, overlay refusal proven
- destructive-operation gates: GUID pins on every helper, no destroy path anywhere

Record these three pendings in the closing note rather than leaving them implicit:

1. Ark scrub completion. HC is down from the planned pause, by design. Close the check only when `zpool status -jp ark` shows FINISHED with 0 errors and `end_time` after the preserved start 1788686258.
2. Cold-boot mount proof. The packaged `zfs-mount.service` unmount/remount rehearsal passed, but no reboot has run with roots at `mountpoint=none`. First reboot should be a deliberate step when SSH credential unlock is attended, followed by `zfs mount` listing all six and `systemctl status zfs-mount`.
3. Quarantined-zvol refreservation release (~266 GB on black-box). Deferred to an explicit user decision; not part of the archive policy.

Housekeeping when closing: front matter still reads `status: open` and `blocked-by: [31]`; the "then create a separate implementation ticket" clause is overtaken, since implementation landed on physical hardware under this ticket. Say so in the closing paragraph.

## Critical closure gaps

None found. The one-shot `-u` volume rename failure was recovered with type-specific GUID-guarded renames and all GUIDs rechecked; that is a procedure note for the README, not an open risk.

No repository files modified. This report is the only file written.
