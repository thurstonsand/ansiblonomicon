---
status: open
type: grilling
blocked-by: [1, 2, 4, 5, 6, 8, 10]
---

# Cutover runbook

## Question

The ordered, verified sequence that takes the machine from TrueNAS-at-old-house to Proxmox-at-new-house.

Assemble from the closed tickets: irreplaceable-subset backup verified → storj drained → final snapshots → shutdown and physical move → BIOS review (VMD) → Proxmox install on boot SSD only → pool import → dataset cleanup (ix-*, .system, retired datasets) → reconcile from repo (storage services, stacks, Plex, agent platform) → verification checklist (pools healthy, Plex HW transcode, shares, stacks up, DNS).

Grill the ordering and failure handling, then execute — this ticket closes when the rebuilt machine is running.

## Progress

Grilled 2026-08-20, round 1. Skeleton adopted:

- **Phase 0 — repo authoring** (now→move): playbook, roles, caddy gateway, stack debridging, terraform/unifi, wizards. Constraint: additive-only — `truenas.yml` and live templates keep working until cutover.
- **Phase 1 — pre-move on live system**: first verified restic→B2 backup of the black-box subset — **DONE 2026-08-21**: repo `b2:pod042:black-box`, snapshot `a21e7e22`, 28.997 GiB, `restic check` clean, sample restore diff-verified (`premove-backup.sh`; re-runnable, dedups). Remaining: UDMP config capture, final exports/snapshots at teardown.
- **Phase 2 — move day** (`teardown.sh` wizard): ordered shutdown → `zpool export` → power off; at new house: fiber/WAS-110 first, BIOS pass (VMD off), Debian netinst — **driven by 2B over the NetKVM console**; human racks, cables, and watches.
- **Phase 3 — bring-up** (`bringup.sh` wizard): bootstrap (ssh+repo) → pool import + rename → `poe pod042` reconcile → ticket-10 dataset rebuild-in-place → verification battery (pools, QuickSync, share, stacks, DNS, alerting heartbeat).
- **Phase 4 — settling**: UDMP wipe + declare (ticket 15), DNS migration, GE completion → storj retirement, ticket 17 purge, CONTEXT.md rewrite.

Round 2 (same day) resequenced Phase 0/4: **the network topology change is deferred past the move entirely.** The UDMP keeps today's VLANs until Phase 4, so the pod042 playbook reproduces the macvlan networks and deploys all stack templates unchanged — move day changes hardware and OS only. Post-move order: caddy gateway + stack-by-stack debridging (live, individually testable) → UDMP wipe + terraform declare → tier model. No cutover branch needed; main remains the only branch. Phase 0 shrinks to: **A** pod042 playbook + storage/alerting/samba roles + carried-over docker plumbing (opus subagent), **D** restic+B2 (opus subagent; human prerequisite: B2 account+bucket+key into the `agent` vault), **C** wizards (2B, after A), **E** VM converge test (2B). Incus (F) and terraform/unifi (G) land post-move.

**Converge gauntlet passed 2026-08-21** (Lima arm64 Debian 13 VM, real ZFS via dkms, mocked Hark/HC): clean converge (627 ok / 0 failed), steady-state 3 changed (all rig artifacts), per-tag runs idempotent, lint clean. Hammer suite: sanoid cuts on black-box only (28 snapshots, ark 0), real scrub under hc-run, hc-run preserves exit status with the notifier dead, zpool-degrade → zed → zedlet → mock-Hark FAULTED alert in 6s, samba writes land `thurston:media 0664/2775`, 12+ containers healthy. 16 minimal fixes landed across 12 files — three were move-day incidents in waiting (docker_stack rsync never copying stack-level plain files; chezmoi pinning `DOCKER_HOST=ssh://truenas`; restic_backup unwired). Untestable in rig, verified on move day instead: smartd (ConditionVirtualization), plex/arr images (amd64-only), host_network, QuickSync. Move-day notes now baked into bringup.sh: file-shaped bind-mount preflight, Mason cold-cache timeout on first run, restic timer fires a real full backup on enable. Full detail: subagent session 01a02287. Standing finding for the post-move dataset rebuild: stack bind mounts reference TrueNAS-era dataset names (`watch`, `apps`) that ticket 10's layout retires — the rebuild must repath the stack templates in the same stroke; until then the media share (`/mnt/ark/media`) is empty because media lives at `ark/watch`.

Decisions: **storj GE risk accepted** — no sequencing around it; node comes up whenever docker does. **Two wizards** (teardown/bringup) with a shared state file, confirm gates before irreversible actions, every machine stage idempotent and resumable; 2B stays engaged during execution — wizards are the known-good path, not the contingency plan. Install is manual-free via NetKVM. Phase 0 parallelized across subagents with converge-testing in a local VM (OrbStack Debian first, TrueNAS VM fallback).
