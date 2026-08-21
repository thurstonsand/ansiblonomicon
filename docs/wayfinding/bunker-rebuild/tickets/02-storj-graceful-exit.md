---
status: open
type: task
claimed: 2b-session
blocked-by: []
---

# Storj graceful exit

## Question

Wind down the storj node (5.2T on `capacity`) before the move. Time-sensitive: graceful exit has a bleed-off period, and extended downtime penalizes the node anyway.

Steps to establish and drive:

- Confirm node eligibility for graceful exit and the current exit procedure/duration.
- Distinguish the *node* (hosting others' data, earning) from any *backup data Thurston stores on storj* — do not cancel or break the backup side until [Cloud backup replacement](04-backup-replacement.md) lands.
- Trigger the exit, monitor to completion, then retire the `storj_node` catalog app declaration and reclaim `capacity/storj-node`.

Resolution records what was done, dates, and any held-back escrow outcome.

## Progress

- 2026-08-19: Confirmed the node/account distinction. Account side: two nightly restic tasks (TrueNAS Cloud Backup) push `capacity/backup/timemachine` and all of `performance` to `sj://windows-backup` — untouched by node exit; account stays until [Cloud backup replacement](04-backup-replacement.md) lands.
- 2026-08-19: Node facts: joined 2024-01-02, earns ~$5–10/mo, outstanding held ≈ $11.49 (units verified against paystubs, 1e-6 USD scale). GE mechanics verified: 30 days online, score ≥ 0.8, irreversible, no piece transfer.
- 2026-08-19: **Graceful exit initiated on all four satellites** (`storagenode exit-satellite` in `ix-storj-node-storj-1`). Only us1 holds data (5.01 TB). Expected completion ~2026-09-18; held pays out next cycle after success. Constraint accepted: node container + `storj.thurstons.house` + port 28967 forward must come back early at the new house; online-score budget tolerates ~6 days total downtime.
- Remaining: monitor `exit-status`, capture completion receipts, retire the `storj_node` catalog app declaration, reclaim `capacity/storj-node` (~5.2T).
