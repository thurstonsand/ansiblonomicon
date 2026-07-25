---
status: closed
claimed: 2B (charting session)
type: grilling
blocked-by: [2]
---

# Self-management loop design

## Question

Design the loop that keeps pod042 current without Thurston: periodic converge from this repo (ansible-pull vs local clone + `poe pod042` under a systemd timer — the repo's poe/uv entrypoints assume a checkout with direnv-resolved secrets, which pull-mode complicates), failure detection, and on-failure agent spin-up that attempts repair autonomously. Pin down: what "failure" means (converge exit code, service health, both), what the repair agent is allowed to change (the box? this repo? open a PR?), how repair attempts are bounded (retries, cost, runaway protection), and how outcomes are recorded. Whether the repair agent is Amp scheduled-task-native or a systemd `OnFailure=` unit that shells into the harness depends on what the Headless Amp capabilities research found.

## Resolution

Grilled 2026-07-24. The loop is **systemd-owned**; Amp is the repair executor and remote surface, not the scheduler (per [Headless Amp capabilities](02-headless-amp-capabilities.md); the `amp --headless` follow-up confirmed that flag is an employee-gated internal executor — `--no-tui` is the public runner mode this design uses).

- **Converge**: persistent checkout on the VM; a systemd timer (daily + manual trigger) runs a wrapper: git fetch + reset to origin/main → `uv run poe pod042` (local connection) → post-converge verify. One code path for human and timer; the checkout doubles as the resident runner's working directory.
- **Failure**: converge exit code **or** post-converge verify failure. The verify script is the executable definition of "pod042 is healthy": key systemd units active (incl. the Amp runner), docker context reachable, NFS mount present, disk headroom. Continuous monitoring deferred as a cheap later upgrade (same script, second timer).
- **Repair authority**: **full autonomy** — the agent may fix the box and push fixes to this repo's main; converge-from-main redistributes them. User's call: "yolo, i can always revert." The repair prompt should still have the agent distinguish box-local (converge-ephemeral) fixes from repo fixes in its report.
- **Bounds**: one attempt per failure fingerprint (hash of failing task/error), ~30min timeout, fail-closed. Repeat of the same fingerprint → alert-only until human ack or repo HEAD changes. No retries — identical input rarely yields a different repair, only spend.
- **Amp updates**: auto-update mode stays on; systemd restarts the runner in a maintenance window so the new binary takes. (Auto chosen over host-managed — accepts Amp's near-daily cadence without wiring an update pipeline.)
- **Record**: journald for wrapper logs; a state dir for last-converge status, fingerprint marker, and repair `--stream-json` transcripts. What gets pushed to Thurston is [Comms channel and remote access](06-comms-and-remote-access.md)'s decision.
