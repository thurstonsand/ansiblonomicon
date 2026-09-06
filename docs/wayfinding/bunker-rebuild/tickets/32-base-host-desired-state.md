---
status: open
type: grilling
blocked-by: [31]
---

# Base host desired state

## Question

Audit the old playbook's base-system behavior and decide what the fresh Debian 13 host should actually declare: package and repository policy, upgrades, users and groups, SSH, login shell, time and locale, kernel or hardware prerequisites, reboot behavior, and retired state. Include the minimum bootstrap state needed before the normal native mise reconcile can take over.

Do not preserve a package or setting merely because Ansible once installed it. Close with an explicit accepted inventory and verification contract; then create a separate implementation ticket.
