---
status: open
type: grilling
blocked-by: [31, 34, 36, 37]
---

# Service portfolio

## Question

Audit every service the old pod042 playbook and stack inventory would start. Decide which services still belong on the rebuilt host, what user-visible contract each retains, what can merge or disappear, and which dependencies or data paths change under `ark`, `black-box`, one Caddy gateway, and the new trust domains.

Do not implement stacks in this ticket. Each retained service or tightly coupled service group graduates into its own desired-state signoff ticket, followed by a separate implementation ticket.
