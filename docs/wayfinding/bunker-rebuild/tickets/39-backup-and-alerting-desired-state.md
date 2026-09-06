---
status: open
type: grilling
blocked-by: [31, 33, 34]
---

# Backup and alerting desired state

## Question

Specify how native mise owns the already-selected restic plus Backblaze B2 backups and Hark plus Healthchecks.io alerting: credentials, schedules, producer interfaces, retention, first-run behavior, restore proof, heartbeat and dead-man coverage, notification failure behavior, and local records.

Use the closed platform decisions as constraints, but audit the Ansible implementation and trial runtime for accidental behavior. Close with external acceptance tests; then create a separate implementation ticket.
