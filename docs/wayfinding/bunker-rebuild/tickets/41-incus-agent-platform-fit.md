---
status: open
type: grilling
blocked-by: [31, 33, 34, 36]
---

# Incus agent platform under native mise

## Question

Fit the accepted pascal and ephemeral-worker design into the native mise host model. Confirm Incus installation and update policy, storage pools, bridges, profiles, project boundaries, image trust, durable instance lifecycle, worker creation and destruction, host resource grants, secrets, and recovery. Identify which state belongs to the host target and which belongs inside an instance.

The agent-platform design is already accepted; reopen only assumptions that conflict with native mise or the final host and network declarations. Close with host and instance interfaces plus acceptance tests; then create a separate implementation ticket.
