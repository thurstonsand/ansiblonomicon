---
status: open
type: grilling
blocked-by: [31]
---

# Secrets and host identity

## Question

Decide pod042's machine identity and secret-delivery model under native mise: hostname and DNS facts, SSH host and operator keys, 1Password service-account bootstrap, secret material allowed on disk, systemd credential delivery, rotation, remote-reconcile authentication, and recovery when the workstation or 1Password is unavailable.

Audit the prior `op_service_account` behavior rather than translating it. Close with explicit ownership and failure behavior; then create a separate implementation ticket.
