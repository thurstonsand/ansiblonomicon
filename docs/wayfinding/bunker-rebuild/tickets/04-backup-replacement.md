---
status: closed
type: grilling
blocked-by: [3]
---

# Cloud backup replacement

## Question

Which backup solution replaces storj, what exactly counts as the irreplaceable subset, and how does it flow there?

Inputs: the shortlist from [Backup solution landscape](03-backup-solution-landscape.md); an inventory of what is actually irreplaceable across `capacity` and `performance` (photos, documents, configs — versus re-acquirable media). Output: chosen provider + tool, dataset list, schedule, and how restore is verified. The pre-cutover backup run gates the [Cutover runbook](09-cutover-runbook.md).

## Resolution

Grilled 2026-08-19, two rounds.

1. **Provider + tool: restic + Backblaze B2.** Continuity, not adoption — TrueNAS Cloud Backup already runs restic (0.16.4) under the hood; the move swaps the storj backend for B2 and the middleware for a repo-declared systemd unit.
2. **Subset rule: `black-box` is backed up offsite; `ark` is re-derivable.** Concretely: docker stack configs (incl. plex, and the *arr databases — which ARE the list of what media should exist), the future `agents` dataset, anypod's db + transcripts (which land on `black-box` per the layout decision). Nothing from `ark` at all: media re-downloads into place because the *arr state says what belongs there. Estimated subset ~20–50G → under $1/mo on B2.
3. **Fresh repos**, matching the new dataset layout. The storj *account* retires once the first B2 backup verifies (independent of the node's graceful exit).
4. **Retention: 7 daily / 4 weekly / 12 monthly; prune and `restic check` monthly.** Source boundary: ZFS snapshot per the landscape research.
5. **Alerting deferred** to [Alerting and notifications](12-alerting-decision.md), fed by the dispatched [Alerting platform landscape](11-alerting-platform-landscape.md) research; failure AND staleness (dead-man) alerts both required.
6. **Device backups (timemachine/windows) are dead**, not targets: no longer operational, stale. Executed 2026-08-19: TrueNAS Cloud Backup task "Devices Backup" deleted; `capacity/backup/timemachine` + `windows` datasets destroyed (1.15T freed); stale `windows` SMB share deleted; remote `sj://windows-backup/mnt/capacity/backup/` repo purge started. Restarting device backups someday goes to the map's fog.

Executed alongside (discovered during subset sizing): cli-proxy-api had 282G of unrotated request logs — `request-log: false` declared in the stack template, deployed, logs purged; space frees as the 6-hourly (3-day) and monthly (1-month) auto-snapshots expire. "Docker configs" true size is ~15G.
