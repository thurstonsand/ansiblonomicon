---
status: open
type: grilling
blocked-by: []
---

# Unattended Loch Highland Atlas backups

## Question

Once [thurstonsand/loch-highland-atlas](https://github.com/thurstonsand/loch-highland-atlas) can capture and restore a complete recovery set by hand, how does pod042 run that capture unattended? Decide the runner, how it deploys from this repo, which credentials it holds and where they come from, where encrypted snapshots land, the cadence and retention, how failures and missed runs alert, and how full restores are exercised. Close with external acceptance tests, then create a separate implementation ticket.

The scope is Atlas scheduling only. Black-box offsite backups and the general producer contract remain with [Backup and alerting desired state](39-backup-and-alerting-desired-state.md); this ticket neither satisfies that ticket nor waits for it. Where the two must share a choice, such as one restic convention, record the choice here as Atlas-scoped and leave the general decision to ticket 39.

## Prerequisite

Not workable until the Atlas repository ships its manual backup and restore tool and proves it with a complete restore into a fresh Lakebed deployment. As of 2026-10-03 no part of that tool has been implemented or pushed; do not assume its interface. This dependency lives in another repository, so it is stated here rather than in `blocked-by`.

## Inputs

- **Recovery set** (decided in the Atlas repository): every home and atlas, editor access, invitations, preferences, future private Matter setup credentials, and the bytes of every currently referenced plan image. Application deployment credentials such as `SNAPSHOT_TOKEN` are reprovisioned separately and are not part of it. The backup decryption key must be held independently of the backup destination and of pod042. Source-controlled synthetic development fixtures are not production backups.
- **Source**: hosted Lakebed at `loch-highland-atlas.lakebed.app`, read through the Atlas repository's tool rather than a parallel client written here.
- **Prior art**: [Cloud backup replacement](04-backup-replacement.md) chose restic plus Backblaze B2 with 7 daily, 4 weekly, and 12 monthly retention, and a sample restore from `b2:pod042:black-box` passed on 2026-08-21. Ticket 39 records that pod042 has had no declared offsite backup since cutover, so treat none of it as live.
- **Alerting**: [Alerting decision](12-alerting-decision.md) fixes Hark plus hosted Healthchecks.io, with scheduled jobs pinging `/start` and `/<exit>` so both failures and missed runs alert.
- **Secrets**: [Secrets and host identity](33-secrets-and-host-identity.md) delivers host credentials through fnox from 1Password.

## Starting proposal

Recommendations from the source conversation, not accepted selections:

- A systemd timer on pod042, declared through native mise, runs the Atlas tool to fetch a complete recovery set from Lakebed.
- restic stores encrypted snapshots in a dedicated B2 repository, separate from black-box.
- Narrowly scoped Lakebed read and B2 write credentials arrive through fnox.
- Healthchecks.io alerts on failures and missed runs.
- Periodic full restores into a scratch deployment verify the backups, not only `restic check`.
- Nightly with 7 daily, 4 weekly, and 12 monthly retention.

Cloudflare R2 is the alternative destination. The existing R2 bucket holds Terraform state and is not an Atlas backup store.
