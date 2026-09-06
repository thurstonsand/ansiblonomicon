---
status: open
type: grilling
blocked-by: [31, 34]
---

# SMB data access

## Question

Decide the exact file-serving contract for pod042 after the dataset rebuild: retained shares, authentication, user and group mapping, ACL behavior, discovery, client compatibility, network exposure, service hardening, and recovery checks. Revisit the prior single `media` share decision if actual clients require more or less.

Audit the Ansible Samba role without assuming parity. Close with client-visible acceptance tests; then create a separate implementation ticket.
