---
status: open
type: grilling
blocked-by: [31, 33, 34, 36]
---

# Incus agent platform under native mise

## Question

Fit the accepted pascal and ephemeral-worker design into the native mise host model. Confirm Incus installation and update policy, storage pools, bridges, profiles, project boundaries, image trust, durable instance lifecycle, worker creation and destruction, host resource grants, secrets, and recovery. Identify which state belongs to the host target and which belongs inside an instance.

The agent-platform design is already accepted; reopen only assumptions that conflict with native mise or the final host and network declarations. Close with host and instance interfaces plus acceptance tests; then create a separate implementation ticket.

## Shared substrate slice (2026-09-09)

The user explicitly pulled the minimum Incus substrate and a blank, fresh Home Assistant OS VM into the Bunker rebuild despite the map's prior smart-home exclusion. [Ticket 49](49-incus-home-assistant-substrate.md) records that bounded implementation. It does not decide or implement pascal, worker profiles, projects, trust grants, secrets, or agent lifecycle. This ticket remains open for that broader agent-platform work.
