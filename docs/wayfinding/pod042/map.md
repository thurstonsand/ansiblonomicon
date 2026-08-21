# Pod042: OpenClaw sunset, dev box rebuild

> **Superseded 2026-08-19** by [bunker-rebuild](../bunker-rebuild/map.md). The pod042 VM retires at that effort's cutover; the Debian host itself takes the pod042 name and the agent platform is redesigned on incus (durable instance **pascal** + ephemeral workers — see [bunker-rebuild ticket 07](../bunker-rebuild/tickets/07-agent-platform-on-proxmox.md)). Salvaged as designs: the self-management loop, the `op` launcher role, the comms design. All remaining tickets closed as overtaken or unresolved ideas; the decision record below stands.

## Destination

OpenClaw (VM, playbook, config, DNS) is fully sunset, and **pod042** — a lean, agent-ready dev VM on TrueNAS — is running: converging itself from this repo on a timer, reaching the TrueNAS Docker daemon over SSH, self-healing via a resident agent, and reporting back to Thurston. Execution is in scope for this map: the destination is the running machine, not just its design docs.

## Notes

- Execution tickets are allowed (charted 2026-07-24; overrides wayfinder's plan-only default).
- Skills to consult: `truenas-docker-ops` for anything touching the NAS; `installing-software` for anything installed on managed machines; `/grill-me` for grilling tickets.
- Salvage posture: fresh playbook, cherry-pick proven roles (sshd, shpool, sessions, agent_harness, chezmoi, `local.truenas.vm`). Do not fork the openclaw playbook wholesale — it accreted (sid pinning, legacy cleanup, inline op wrapper).
- Standing decisions from charting:
  - Name: **pod042** (hostname, playbook, `poe pod042`, DNS).
  - Docker access shape: Docker context over SSH (`DOCKER_HOST=ssh://truenas`), no daemon reconfiguration on TrueNAS.
  - Resident harness candidate: headless Amp; its actual capabilities (scheduling, remote access) are a research ticket, not an assumption.
  - The old OpenClaw state is disposable; everything worth keeping is in git.

## Decisions so far

<!-- one line per closed ticket -->

- [OS selection for pod042](tickets/01-os-selection.md) — Debian 13 stable on its generic cloud image; keep fast tools in their native managers, use only explicit single-package backports, and avoid sid.
- [Headless Amp capabilities](./tickets/02-headless-amp-capabilities.md) — Public `--no-tui` runners and web/mobile thread control work; hidden `--headless` is unsupported and does not solve scheduler placement, alerts, or service-auth bounds.
- [Docker-over-SSH workflow](./tickets/03-docker-over-ssh-workflow.md) — admin user + dedicated 1Password-tracked key; no coexistence rules (trusted homelab); symmetric-path NFS dataset (`/mnt/performance/pod042`) for bind mounts; builds on the NAS daemon; VM-local dev is primary, Docker auxiliary.
- [Self-management loop design](tickets/05-self-management-loop.md) — systemd-owned loop: daily checkout-reset + `poe pod042` + verify script; failure → one fingerprint-bounded `amp -x` repair with full autonomy (may push to main); Amp auto-updates with runner restart; journald + state dir as the record.
- [Agent-native secrets tooling](tickets/12-agent-native-secrets-tooling.md) — Extract a minimal service-account `op` launcher role; use `op inject` for converge and `op run` plus systemd credentials for narrowly injected services, without porting OpenClaw's resolver.
- [Secrets bootstrap for pod042](tickets/04-secrets-bootstrap.md) — reuse OpenClaw's SA (agent vault covers ~all refs); personal SSH key for git push; shared `AMPCODE_API_KEY`; delivery via the new `op` launcher role per the secrets research; SA gets vault write access so the agent can self-provision credentials.
- [Comms channel and remote access](tickets/06-comms-and-remote-access.md) — Discord webhook for alerts (Amp-independent dead-man's channel); Amp web/mobile threads as the conversational surface; Amp remote terminal instead of an SSH tunnel app (truenas-ssh + LAN hop as fallback); `pod042.thurstons.house` reserved as placeholder.
- [Playbook and VM provisioning design](tickets/07-playbook-and-vm-design.md) — 4c/16G, 80G zvol on performance, fresh identity at static .94 (`.91` was occupied), manual-once cloud-image provisioning, audited role cherry-picks, three new roles; full design consolidated in [Pod042 Dev Box](../../designs/20-pod042-dev-box.md) (Accepted).
- [Migrate VM storage off the SSD pool](tickets/10-migrate-vm-zvols-to-capacity.md) — Retained the stopped OpenClaw reference image on `capacity` and freed 141.5 GiB from the `performance` SSD pool.

## Not yet specified

## Out of scope

<!-- work ruled beyond the destination -->
