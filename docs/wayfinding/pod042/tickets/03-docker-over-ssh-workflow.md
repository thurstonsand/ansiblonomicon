---
status: closed
claimed: 2B (charting session)
type: grilling
blocked-by: []
---

# Docker-over-SSH workflow

## Question

The shape is decided — `DOCKER_HOST=ssh://truenas` from pod042 — but the workflow around it is not. Which TrueNAS user and SSH key does the context use, and what is its blast radius (the docker socket is root on the NAS)? How does agent-driven container work coexist with the ansible `docker_stack` role's managed stacks — naming conventions, networks, a rule for what pod042 may touch? Where do bind mounts come from, given paths resolve on the NAS filesystem (does pod042 need NFS visibility into `/mnt/performance/docker`, or a dedicated scratch dataset)? Do images build on the NAS daemon, and is that acceptable? Resolve into a documented contract between pod042 and the TrueNAS Docker daemon.

## Resolution

Grilled 2026-07-24. The contract:

- **Identity**: reuse the existing `admin` user on TrueNAS with a **dedicated pod042 SSH key** — revocation is removing one key from `authorized_keys`. The private key is tracked in 1Password (agent vault) and deployed to pod042 via SecretRef during converge; wiring details land in [Playbook and VM provisioning design](07-playbook-and-vm-design.md).
- **Coexistence**: no rule. Homelab, trusted agent, single daemon shared with the ansible-managed stacks. `poe truenas` heals any managed-stack drift if the agent ever misbehaves.
- **Storage**: symmetric-path dataset. A dedicated NAS dataset (working name `/mnt/performance/pod042`) is NFS-exported and mounted on pod042 at the **identical path**, so bind mounts written on pod042 resolve the same on the NAS. Agent rule: bind mounts only under that path; named volumes for throwaway state. Read-only NFS into `/mnt/performance/docker` deliberately omitted from v1 — `ssh truenas` covers managed-stack debugging.
- **Builds**: `docker build` executes on the NAS daemon (context ships over SSH); accepted — the docker_stack role already builds there. Cache pruning rides along in the self-management loop if needed.
- **Framing**: local development *in the VM* is the primary mode; the Docker context is auxiliary — for support services (a Postgres, a Redis) a dev task needs, not the dev environment itself.
