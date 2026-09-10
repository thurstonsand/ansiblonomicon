---
status: open
type: grilling
blocked-by: [31, 33, 34]
---

# Backup and alerting desired state

## Question

Specify how native mise owns the already-selected restic plus Backblaze B2 backups and Hark plus Healthchecks.io alerting: credentials, schedules, producer interfaces, retention, first-run behavior, restore proof, heartbeat and dead-man coverage, notification failure behavior, and local records.

Use the closed platform decisions as constraints, but audit the Ansible implementation and trial runtime for accidental behavior. Close with external acceptance tests; then create a separate implementation ticket.

## Progress

Deferred by user decision on 2026-09-10. Existing host monitoring and alerting remain active, but pod042 currently has no declared offsite backup. The last verified black-box backup was the 2026-08-21 pre-cutover snapshot created on TrueNAS. Offsite application backup and restore policy waits until the user revisits it.
