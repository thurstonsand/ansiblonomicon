---
status: closed
type: grilling
blocked-by: [31, 34]
---

# SMB data access

## Question

Decide the exact file-serving contract for pod042 after the dataset rebuild: retained shares, authentication, user and group mapping, ACL behavior, discovery, client compatibility, network exposure, service hardening, and recovery checks. Revisit the prior single `media` share decision if actual clients require more or less.

Audit the Ansible Samba role without assuming parity. Close with client-visible acceptance tests; then create a separate implementation ticket.

## Resolution

Pod042 exposes exactly one read/write SMB share, `media`, rooted at `/mnt/ark/media`. It deliberately does not export either pool root, `/mnt/black-box`, application state, rendered credentials, legacy datasets, former device-backup datasets, or separate media subdirectories. SSH remains the application-administration path. One share gives Finder and other clients a stable namespace while preserving the storage split internally.

Only the existing `thurstonsand` account authenticates. Samba forces new content into group `media` with group-write and setgid directory semantics, matching containers' shared GID 3000 without rewriting imported ownership. The password remains an Agent-vault SecretRef rendered into a root-only authentication file; a final reconciler changes Samba's independent password database only when the declared credential no longer authenticates.

The server listens on direct SMB3 port 445 on loopback and `enp5s0`. NetBIOS, guest access, printers, directory-service roles, and discovery remain disabled; clients use UniFi's local `pod042.thurstons.house` record or `10.10.10.42`. YoRHa's existing all-protocol administration policy admits SMB. Lunar Tear remains limited to 80, 443, and 32400, so household and guest devices do not receive file access. Native mise owns packages, configuration, account convergence, `smbd`, and stopped/disabled `nmbd`, Winbind, and Samba AD DC services through the separate [Implement SMB data access](47-implement-smb-data-access.md) ticket.
