---
status: closed
type: implementation
blocked-by: [37]
---

# Implement the pod042 container platform

## Objective

Implement the accepted [Container platform desired state](37-container-platform-desired-state.md): install and configure Docker through native mise, establish its storage, identity, network, mount-ordering, Compose, secret, update, observability, and operator contracts, and prove the platform with a disposable canary.

## Execution boundary

Work from the running pod042 host without invoking its retired Ansible playbook. Preserve equivalent guarded local and remote reconciliation, serial failure, and exact pushed-revision checks. Audit the old `docker_stack` role for migration evidence, but do not port its machinery by default.

This ticket establishes only the shared platform, resident Watchtower, native Netdata, and a disposable canary. Do not start preserved application stacks, migrate their data, publish a Cloudflare route, or change Plex's router forward. Those belong to the service portfolio and per-project implementation tickets. Do not perform broad Docker pruning or remove bind-mounted application data.

## Completion evidence

- [x] Native mise installs the official Docker CE packages, owns daemon settings and service state, orders container startup after both ZFS application mountpoints, and converges unchanged locally; the guarded remote path remains equivalent and test-covered.
- [x] Rootful operator access, disjoint Docker address pools, shared ingress network, logging limits, live restore, and the no-TCP-socket boundary match the approved declaration.
- [x] Native `[bootstrap.compose]` declarations provide private definitions and interpolation environments, Compose validation, pull/build/recreation policy, serial health-aware apply, model-hash convergence, and explicit retirement.
- [x] Resident Watchtower has the declared 04:00 all-registry-container update, dependency, cleanup, exclusion, and Hark notification policy. Do not block completion on observing a real image update.
- [x] Native Netdata observes host/ZFS/systemd/Docker state, emits a proven Hark test alert, and exposes its local MCP interface without granting automatic remediation. Its dashboard binds locally and is smoke-tested through the operator path; trusted Caddy exposure waits for the ingress project and must never enter the public Cloudflare tunnel.
- [x] A disposable Compose canary deploys healthy, is visible to Netdata and synchronous declared-state verification, then retires without leaving its project, network, generated definition, or durable data behind.
- [x] Focused tests, format/lint/type checks, Docker/Compose configuration validation, and repository whitespace checks pass. Record unrelated failures from broader repository checks exactly rather than weakening checks.

## Deferred evidence

Natural operation will prove reboot behavior and mount ordering. Schedule a one-time Watchtower spot-check for one week after real registry-backed application projects begin running. Per-service routes, data ownership, health behavior, and restoration are accepted in their own implementation tickets.

## Resolution

Implemented directly on pod042 on 2026-09-07. Native mise installed Docker CE 29.8.0, containerd 2.3.4, Compose 5.5.1, and Netdata 2.11.0 from fingerprint-pinned official repositories. Docker is rootful and socket-only, uses `/var/lib/docker`, allocates `10.42.0.0/16` in `/24` networks, waits for both approved ZFS mountpoints, and exposes only the restricted loopback socket proxy. The operator belongs to `docker` and `media`; Netdata does not retain Docker-group access.

Native mise installs each private Compose definition and interpolation environment, then owns project validation, pulls, model-hash drift, health, recreation, orphan policy, and retirement through first-class `[bootstrap.compose]` resources. Its status reports the platform converged with two running and two healthy containers. The resident platform project runs a healthy restricted Docker socket proxy and healthy Watchtower with a daily 04:00 schedule, all-running-container scope, Compose dependency ordering, cleanup, and update/failure-only Hark reports.

Native Netdata reported Docker API and cgroup metrics for the platform and canary, both ZFS pools, and systemd units with zero warning or critical alarms. Netdata calls the shared host `storage-alert` transport through the narrow `alerting` group; the duplicate Netdata-only Hark sender and credential were retired, and the shared sender delivered a live test as `netdata`. The local dashboard HTML and live API passed smoke checks, and the local HTTP MCP server completed a v2025-03-26 initialize handshake as Netdata v2.11.0. The Agent is claimed to Netdata Cloud through a declarative credential, and its custom pod042 operations dashboard was browser-verified. Bearer protection remains disabled on the local Agent listener; its direct Caddy route is restricted to trusted source networks and does not enter the public Cloudflare tunnel, while Netdata Cloud owns authentication for remote dashboard access.

An Alpine 3.22 canary became healthy, passed synchronous verification, and appeared in Netdata. It then converged through explicit `absent` state before its temporary declaration and managed source were removed. Readback found no canary container, network, installed definition, state record, durable data, or image. Focused tests, Ruff, basedpyright, Compose validation, repository whitespace checks, and the final live no-op reconcile passed. The broader `mise run check` reached unrelated existing failures from an unavailable Wrangler executable and Amp TypeScript compiler plus Pi TUI export drift. The guarded workstation-to-host route retains focused test coverage but was not re-executed because no workstation was available; the same host-local target performed the live convergence.
