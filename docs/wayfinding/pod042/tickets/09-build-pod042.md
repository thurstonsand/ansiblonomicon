---
status: open
claimed: build-handoff-session
type: task
blocked-by: [5, 6, 7]
---

# Build pod042

> Unblocked from [Sunset OpenClaw](08-sunset-openclaw.md): pod042 uses a fresh IP/MAC and its own zvol, so nothing waits on OpenClaw's deletion.

## Question

Execute the accepted designs: create the VM on TrueNAS, provision the OS, run the new playbook to convergence, verify the Docker-over-SSH context against the NAS daemon, stand up the resident harness and self-management timers, and prove the loop end to end — a deliberate converge failure that triggers the repair agent and a report that reaches Thurston. Done when pod042 survives a reboot unattended and the evidence is shown.

## Progress

- 2026-07-25: Gate 3 implementation plan approved. Phase 1 started with an explicit handoff boundary: bootstrap manually through the first local `poe pod042` converge, then continue execution from a new Pi session inside the pod042 checkout. `poe pod042` is local-only; no workstation-driven remote-Ansible path will be built.
- 2026-07-25: Phase 1 repository tracer bullet implemented and documented. Production-profile Ansible lint, Python formatting/lint/types, 132 Python tests, Pi package lint/types, syntax checks, local-only Poe refusal, and a read-only scoped TrueNAS check passed. The check caught and prevented a ZFS namespace collision; the shared dataset remains `performance/pod042` and the boot zvol is `performance/pod042-boot`. No pod042 NAS resources exist yet.
- 2026-07-25: Read-only adversarial bootstrap review completed. Corrected all first-run blockers before apply: armored apt keys now use `.asc` keyrings, GitHub's published Ed25519 host key and the 1Password SSH-agent socket are explicit, token transfer rejects missing/empty input without putting the value in argv, and the role rejects an empty persisted token. The NFS export is scoped to `.91` with matching `1000:1000` POSIX identity and ordinary root semantics.
