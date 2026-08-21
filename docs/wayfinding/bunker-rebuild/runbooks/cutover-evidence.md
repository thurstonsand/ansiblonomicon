# Cutover evidence dossier

What has been proven, how, and where the residual risk lives. Assembled 2026-08-21, five days before the move. The contract: evidence replaces line-by-line review.

## Backup chain (ticket 04) — PROVEN LIVE

- Repo `b2:pod042:black-box` on bucket `pod042` (private, no SSE, lifecycle keep-only-last-version — set and verified via API).
- Snapshot `a21e7e22`, 28.997 GiB: docker configs (all stacks incl. the *arr DBs), plex config (minus regenerable `Media/`), anypod db + transcripts.
- `restic check`: no errors. Sample restore pulled from B2 and `diff -r`'d clean against source.
- Sources were ZFS snapshots staged at post-move paths, so the repo remains valid for the rebuilt host.
- Credentials: op item `Backblaze` (agent vault), all four fields exercised by actual use.

## Alerting (ticket 12) — PROVEN LIVE

- Direct Hark webhook → iPhone: delivered promptly, including while idle.
- Healthchecks check lifecycle driven end-to-end: `/start` → exit-1 (down) → success (up); both transitions delivered to the phone through the HC→Hark webhook integration.
- Approvals confirmed Pro-gated by live API test; free tier covers all monitoring producers.

## Playbook converge (workstream E gauntlet) — PROVEN IN RIG

Rig: Lima VM `pod042test` (arm64 Debian 13, real kernel, ZFS via zfs-dkms, file-backed pools named `ark`/`black-box`, mocked Hark/HC endpoints, dummy VLAN parents). Left intact for inspection.

- Full converge from bare Debian: 627 ok / 0 failed.
- Idempotency: steady state 3 changed, each an explained rig artifact (smartd blocked by `ConditionVirtualization`, two crash-looping amd64-only images).
- Per-tag partial runs (`sanoid`, `samba`, `alerting`, `scrub`, `zed`, `restic`, `smartd`): all converge, all idempotent.
- 16 minimal fixes were required and are folded in; the three that would have been move-day incidents: docker_stack's rsync silently never copied stack-level plain files; chezmoi pinned `DOCKER_HOST=ssh://truenas` on pod042; restic_backup was never wired into the playbook.

## Storage behavior (ticket 08 design) — PROVEN IN RIG

- sanoid: 28 snapshots cut on black-box per policy; **zero** on ark, as designed.
- Scrub: real scrub executed through the systemd unit under `hc-run`, correct check pings.
- Producer contract under failure: with the notification endpoint dead, jobs still reported true exit statuses (0/1/42) — notification failure cannot mask job failure.
- zed: forced vdev fault produced a phone-payload (`ZFS vdev FAULTED in black-box` + full `zpool status`) through the zedlet within 6 seconds; pool restored clean.
- samba: authenticated write landed `thurston:media 0664`, mkdir `2775` — ticket 10's permission model observed in the wild.

## Not provable before move day (and how each is covered)

| Surface | Why untestable | Coverage |
|---|---|---|
| Real pool import/rename | Pools exist once | Confirm-gated wizard stage with `zpool import` preview; `premove-final` snapshots; metadata-only operation |
| QuickSync `/dev/dri` | No iGPU in rig | bringup battery check + acceptance-lap transcode test |
| smartd | `ConditionVirtualization=no` | Live check added to bringup battery |
| plex/arr images | amd64-only | Compose render/deploy path proven; images are the production ones on real hardware |
| host_network role | Would sever rig connectivity | Structure replicated byte-for-byte from live NAS topology (verified against `ip -d link` output); macvlan creation proven over dummies |
| NVMe visibility post-VMD-off | BIOS setting | Pools are ZFS-labeled; device path changes are irrelevant to import |

## Known first-run behaviors (expected, not failures)

- Mason/neovim may exceed its 600s timeout on a cold cache — re-run.
- `restic-backup.timer` fires a real full backup immediately on enable (`Persistent=true`) — intended; ~29G re-read, small upload via dedup.
- The media share is empty until the post-move ticket-10 dataset rebuild relocates media from `ark/watch` to `ark/media` (the rebuild repaths the stack templates in the same stroke).
