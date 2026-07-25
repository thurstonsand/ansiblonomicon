---
status: closed
claimed: 2B (charting session)
type: grilling
blocked-by: [1, 3, 4]
---

# Playbook and VM provisioning design

## Question

Design pod042's repo presence end to end: the `local.truenas.vm` entry (sizing — the old 2-core/12GB/100GB zvol was generous for a box that outsources Docker to the NAS; NIC on br0; reuse 192.168.1.90 or take a fresh IP), first-boot provisioning path (cloud image + cloud-init vs installer), and a fresh minimal playbook cherry-picking proven roles (sshd, shpool, sessions, agent_harness, chezmoi, language_tools as warranted) plus the new pieces from the docker-workflow, secrets, and self-management decisions. Includes `poe pod042` task wiring, inventory target, and config file layout. Exit with a Gate 2 design doc ready to execute against.

## Resolution

Grilled 2026-07-24. Decisions: 4 cores / 16G (min 8G); 80G zvol on `performance` (freed by the OpenClaw migration); fresh network identity — new MAC, static 192.168.1.91 via cloud-init (`.90` stays with the dormant OpenClaw image); provisioning is manual-once from the Debian cloud image + NoCloud seed ISO, documented at build, with the playbook owning everything from first SSH (SPICE-by-subagent investigated only if needed); carried roles audited individually, not blind-copied — sshd, sessions, agent_harness (+ consider a pod042 provisioning skill), chezmoi (remap openclaw conditionals), language_tools (fresh curated list), shpool, tmux plugins, terminal_theme; motd dropped; system_maintenance transformed into the converge loop rather than carried; new machinery as three roles (`op_service_account`, `converge_loop`, `amp`) with docker context + NFS as inline tasks, judged against role bloat at build time.

Gate 2 design doc: [Pod042 Dev Box](../../../designs/20-pod042-dev-box.md) — consolidates the whole effort's decisions. Accepted.

Build-time amendment (2026-07-25): UniFi revealed that `.91` was already a live static reservation for an Apple device. Pod042 moved to reserved `192.168.1.94`; the fresh MAC and all other VM decisions are unchanged.
