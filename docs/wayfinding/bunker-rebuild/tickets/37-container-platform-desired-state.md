---
status: open
type: grilling
blocked-by: [31, 34, 36]
---

# Container platform desired state

## Question

Decide how native mise owns Docker and deploys services: repository and package policy, daemon settings, operator access, config-tree identities, Compose rendering and validation, image pull policy, secrets, dependencies, health checks, rollback, per-stack partial reconciliation, and retirement. Replace the old macvlan assumptions with the decided host-network model.

Audit the `docker_stack` role and its move-day fixes, but do not translate its implementation by default. Close with a deployment interface and smoke-test contract; then create a separate implementation ticket.
