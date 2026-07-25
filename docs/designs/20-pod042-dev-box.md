# Pod042 Dev Box

## Status

Accepted

## Decision Summary

Replace the retired OpenClaw VM with **pod042**: a lean Debian 13 dev VM on TrueNAS that converges itself from this repo on a systemd timer, self-heals via a resident Amp agent, reaches the TrueNAS Docker daemon over SSH, and reports to Thurston over Discord. The key tradeoff throughout: buy capabilities from first-party surfaces (Amp threads, op CLI, systemd) instead of maintaining a custom gateway — the maintenance burden of custom glue is what killed OpenClaw.

This doc consolidates the decisions charted in [docs/wayfinding/pod042/](../wayfinding/pod042/map.md); individual tickets there hold the full reasoning trail.

## Problem Statement / Background

OpenClaw (design docs 10, and the openclaw playbook) was an agent-gateway VM: a custom Telegram/web gateway wired to agent harnesses. It was unstable, seldom used, and a pain to maintain — the playbook accreted (sid pinning, inline op bootstrap, legacy cleanup tasks) and the gateway was bespoke infrastructure with a maintenance bill. It has been shut down (VM stopped, autostart off, image retained on the `capacity` pool as reference until deletion).

What is actually wanted is a **dev box**: a light Linux VM to offload dev tasks to, with first-class network connectivity (including driving the NAS's Docker daemon), that keeps *itself* current and healthy so it can be ignored for weeks and trusted when needed.

## Goals

- A lean, headless dev VM that a resident agent and Thurston can both drive from anywhere
- Self-managing: converges from this repo unattended; failures trigger an autonomous repair agent; outcomes reach Thurston without polling
- Docker capability without a VM-local daemon: dev containers run on the TrueNAS daemon
- Rebuildable: losing the VM is an inconvenience, not an incident

## Non-Goals

- No custom gateway (Telegram/web) — Amp's first-party surfaces replace it
- No VM-local Docker daemon
- No web service on day one (`pod042.thurstons.house` is reserved but unbound)
- No mechanical sandboxing of the agent — trusted homelab, convention over enforcement

## Exposed Shape

- **`poe pod042`** — the on-VM human entrypoint; same local-only playbook the timer runs (check/tags args like other targets); administration from another machine starts with `ssh pod042`
- **`ssh pod042`** (LAN) — direct shell; remote access is Amp's remote-control terminal, with `truenas-ssh` → LAN hop as fallback when the runner is down
- **Amp web/mobile threads** — the conversational surface to the resident runner (`amp --no-tui` in the repo checkout)
- **Discord webhook** — outbound-only alert channel: converge failures, repair reports, fingerprint-repeat alerts (with thread links)
- **`DOCKER_HOST=ssh://truenas`** — docker/compose CLI on pod042, daemon on the NAS; bind mounts only under the symmetric path
- **`/mnt/performance/pod042`** — one dataset visible at the identical path on both NAS and VM (NFS)
- **The agent vault (1Password)** — read *and write* via service account; the agent self-provisions credentials (`op item create` + `.secrets.jsonc` ref)
- **This repo's `main`** — the box's desired state; the repair agent may push to it

## Design Decisions

### 1. OS: Debian 13 stable, generic cloud image

Boring base, fresh tools elsewhere: mise/uv/npm/cargo/go own fast-moving tooling; backports only ever per-package; **no sid pinning** (the tmux-from-sid pattern is explicitly retired). Arch's pacman/AUR freshness was evaluated and lost: Arch's own maintenance doctrine (read the news before `-Syu`, no partial upgrades) requires a human, which disqualifies it for unattended operation. Ubuntu LTS minimal is the runner-up. ([OS ticket](../wayfinding/pod042/tickets/01-os-selection.md))

### 2. Self-management: systemd-owned loop, Amp as executor

A daily systemd timer runs: git fetch/reset to `origin/main` → `uv run poe pod042` → post-converge verify script (units active incl. runner, docker context reachable, NFS mounted, disk headroom). Failure of either triggers **one** repair run: `amp -x --stream-json` with full autonomy — box changes and pushes to `main` both allowed ("yolo, i can always revert"). Bounded by failure fingerprint: a repeat of the same failure alerts without spending agent credits until human ack or a new commit. Record: journald + a state dir. Amp auto-updates itself; systemd restarts the runner in a maintenance window. Amp's cloud Automations are *not* the scheduler — research could not prove they target a specific self-hosted runner; `amp --headless` is employee-gated and unusable. ([loop ticket](../wayfinding/pod042/tickets/05-self-management-loop.md), [Amp research](../wayfinding/pod042/assets/amp-capabilities.md))

### 3. Docker: SSH context to the NAS daemon, symmetric-path storage

`DOCKER_HOST=ssh://truenas` using the `admin` user with a dedicated 1Password-tracked key. No coexistence rules with managed stacks — trusted agent; `poe truenas` heals drift. The bind-mount trap (paths resolve on the NAS) is dissolved, not managed: dataset `/mnt/performance/pod042` NFS-mounted in the VM at the identical path; bind mounts live only there. The NFS export is restricted to `192.168.1.94`; the dataset and guest user share numeric identity `1000:1000`, while guest root remains root so `sudo` has ordinary local-filesystem semantics. Builds execute on the NAS daemon. VM-local dev is the primary mode; Docker is auxiliary (support services like a scratch Postgres). ([docker ticket](../wayfinding/pod042/tickets/03-docker-over-ssh-workflow.md))

### 4. Secrets: agent-vault service account, op-native delivery, self-provisioning

Reuse OpenClaw's service account (agent vault already holds ~all `.secrets.jsonc` refs), upgraded to **write access** so the agent can provision its own credentials. Delivery: a minimal reusable `op_service_account` launcher role; `op inject` fills the converge `.env`; systemd services get narrow `op run`/systemd-credential injection. The Amp runner never receives the broad `.env` or the SA token. OpenClaw's custom SecretRef resolver retires unported. Deliberate risk acceptances, recorded: personal SSH key on the box for git push; `AMPCODE_API_KEY` shared with the cli-proxy-api stack. ([secrets ticket](../wayfinding/pod042/tickets/04-secrets-bootstrap.md), [secrets research](../wayfinding/pod042/assets/agent-native-secrets.md))

### 5. Comms: Amp threads for conversation, Discord for alerts

Amp web/mobile is the conversational surface; the runner makes pod042 threads startable/steerable from anywhere. Alerts go out-of-band via a Discord webhook (one HTTPS call from the wrapper) precisely so the failure path never depends on the harness being healthy. No SSH tunnel app successor for openclaw-ssh — Amp's remote terminal covers remote shell, `truenas-ssh` is the break-glass path. ([comms ticket](../wayfinding/pod042/tickets/06-comms-and-remote-access.md))

### 6. VM: 4 cores / 16G (min 8G), 80G zvol on `performance`, fresh identity

New MAC, static 192.168.1.94 via cloud-init; `.90` stays with the dormant OpenClaw image, and the originally selected `.91` was corrected at build time after UniFi revealed an active Apple-device reservation there. Provisioning is **manual-once**: hand-place the cloud image and NoCloud seed ISO on the NAS (steps documented at build; SPICE only if something goes wrong — investigate subagent-drivable SPICE then, not before). The playbook owns everything from first SSH. A scripted rebuild pipeline was considered and deferred — worth revisiting if a rebuild actually happens. ([playbook ticket](../wayfinding/pod042/tickets/07-playbook-and-vm-design.md))

### 7. Repo shape: fresh playbook, audited cherry-picks, three new roles

`ansible/playbooks/pod042.yml` + `pod042.config.yml` + a local inventory target + `poe pod042`. Carried roles — **each audited at porting time, not blind-copied**: sshd, sessions, agent_harness, chezmoi (remap openclaw conditionals), language_tools (fresh curated list; audit OpenClaw's apt/tool set for what earns a slot), shpool, tmux plugins, terminal_theme (mirror). Dropped: motd, openclaw_monitors, the gateway, sid pinning. system_maintenance is *transformed, not carried*: apt upgrade folds into the converge loop rather than a parallel timer. New roles, judged against role-bloat at build time: `op_service_account`, `converge_loop`, `amp` (install + resident runner + the arbitrary-directory runner tool from the [runner-tool prototype](../wayfinding/pod042/tickets/11-arbitrary-directory-runner-tool.md)); docker context + NFS mount stay inline playbook tasks. A pod042-specific agent skill for provisioning global tools is worth authoring alongside agent_harness.

### 8. Execution locality and bootstrap handoff

`poe pod042` supports execution **on pod042 only**. There is no remote-Ansible mode: a human elsewhere SSHes to the VM and runs the same local playbook used by the converge timer. This keeps the primary development and management path honest instead of preserving a second workstation-driven path only for first provision.

The pre-Ansible bootstrap is deliberately ad hoc and manual-once, not an Ansible role or maintained bootstrap script. The operations runbook records the exact cloud-image, NoCloud seed, first-login, agent-forwarded clone, and initial `uv` commands, but the deferred scripted-rebuild alternative remains deferred. The current build session owns that path through the first successful local `poe pod042` converge, which installs the managed Pi runtime; execution then moves into a new Pi session started from the checkout on pod042. Transitioning earlier would require installing the agent outside the desired-state playbook merely so it could run that playbook.

## Edge Cases & Failure Modes

- **Converge fails repeatedly on the same error:** one repair attempt, then alert-only per fingerprint; new commit or human ack re-arms
- **Repair agent runs away:** 30-min timeout, one attempt, fail-closed to Discord
- **Amp/Amp Server down:** converge and alerting unaffected (systemd + Discord); only conversation/remote-terminal degrade; break-glass via truenas-ssh
- **VM dies entirely:** rebuild from cloud image + documented seed steps + playbook; dev state under `/mnt/performance/pod042` survives on the NAS
- **Old OpenClaw image booted for reference:** no IP/MAC collision (fresh identity)
- **Agent overwrites its own box-local fix:** converge reset is by design; repair prompt requires the agent to say when a fix is box-local-only so the repo fix follows

## Alternatives

### Amp cloud Automations as the scheduler

- **Status:** Open
- **Open Issue:** runner-targeted dispatch unproven from primary sources
- **Discussion:** would replace the systemd timer for agent-driven maintenance
- **Next step:** disposable-runner experiment; if an Automation provably executes on a chosen `--no-tui` runner, revisit

### Rebuilding a two-way chat gateway (Telegram/Discord)

- **Status:** Rejected
- **Decision:** the custom gateway was OpenClaw's failure mode; Amp threads provide the surface with zero maintenance

### Immutable/atomic OS (CoreOS, MicroOS, NixOS) and Arch family

- **Status:** Rejected
- **Decision:** lifecycle or management-model mismatch with ansible-converge and unattended operation; detail in the [OS research asset](../wayfinding/pod042/assets/os-selection.md)

### Scripted image+seed rebuild pipeline

- **Status:** Deferred
- **Discussion:** reproducible VM creation is attractive but speculative until a rebuild actually occurs; manual steps are documented instead

## Implementation Plan

- [ ] Phase 1: Establish the boot-to-on-VM-agent tracer bullet
  - Goal: In this session, reach a fresh Debian 13 pod042 shell, clone this repo, complete the first local `poe pod042` converge, and transfer execution to a managed Pi session running from the VM checkout.
  - Files: `ansible/inventory/targets/group_vars/truenas.yml`, `ansible/playbooks/truenas.yml`, `ansible/inventory/targets/pod042.yml`, `ansible/playbooks/pod042.yml`, `ansible/pod042.config.yml`, `pyproject.toml`, a new `ansible/roles/op_service_account/`, the minimum pod042 generalization in `scripts/init-secrets.py`, `ansible/roles/chezmoi/`, and `ansible/roles/agent_harness/`, plus a new pod042 operations runbook under `docs/operations/`.
  - Work: Declare the durable 80 GiB `performance` zvol, 4-core/16 GiB/min-8 GiB VM, fresh MAC, autostart, pod042 dataset, and NFS export; add a local-only inventory, deliberately thin first-converge playbook, and Poe entrypoint; implement the reusable runtime `op` launcher needed by that converge; with Thurston, use documented ad-hoc commands—not a bootstrap role or retained script—to place the Debian generic cloud image and NoCloud seed ISO, boot at static `192.168.1.94`, reach the first shell, clone through forwarded SSH-agent credentials, seed the existing service-account token without exposing it in process arguments, install `uv`, and run `poe pod042` locally; use SPICE only if cloud-init or SSH fails; start a new Pi session in the checkout with a self-contained handoff for all later phases.
  - Validation: Run Ansible syntax and production-profile lint checks; apply the scoped TrueNAS path; show the VM definition, zvol, dataset/export, successful cloud-init, SSH shell, agent-forwarded clone, local Ansible connection, successful first converge, managed `pi` executable and configuration, and one unattended reboot; complete the boundary only after the on-VM Pi session starts in the correct checkout and acknowledges the remaining mission.

- [ ] Phase 2: Build the audited development baseline
  - Goal: Turn the tracer VM into the intended lean dev environment without carrying OpenClaw's accumulated machinery.
  - Files: `ansible/playbooks/pod042.yml`, `ansible/pod042.config.yml`, carried role/task files under `ansible/roles/` and `ansible/tasks/`, relevant Chezmoi templates, and a new pod042 provisioning skill under `agents/`.
  - Work: Audit and integrate sshd, sessions, agent_harness, chezmoi, language_tools, shpool, tmux plugins, and terminal_theme individually; generalize hostname-specific OpenClaw paths only where pod042 needs them; curate the Debian apt and language-tool lists; install the Docker client without a local daemon; keep motd, sid pinning, OpenClaw monitors, and gateway code out.
  - Validation: Run focused role/tool tests plus `uv run poe lint:ansible`; converge twice to prove idempotence; smoke-test the selected shells, tools, sessions/shpool, agent resources, dotfiles, tmux plugins, and terminal-theme mirror; prove no Docker daemon is installed or active locally.

- [ ] Phase 3: Complete the secrets, Git, Docker, and storage boundaries
  - Goal: Give pod042 its durable credentials and NAS capabilities while keeping the resident agent outside the broad repository secret cache and service-account bearer token.
  - Files: `ansible/roles/op_service_account/`, `scripts/init-secrets.py`, `ansible/roles/chezmoi/`, `.secrets.jsonc`, pod042 configuration/playbook files, TrueNAS SSH-key management, and the pod042 operations runbook.
  - Work: With Thurston, upgrade/reissue the retained OpenClaw service account for agent-vault write access; finish and test generic `op inject` and Chezmoi use beyond the Phase 1 bootstrap path; create a dedicated pod042→TrueNAS SSH key, store its private key in the agent vault, and authorize its public key for TrueNAS `admin`; deploy the deliberately accepted personal GitHub SSH identity so later unattended fetch/push no longer depends on agent forwarding; configure the NFS mount at `/mnt/performance/pod042` and `DOCKER_HOST=ssh://truenas`.
  - Validation: Run role and secrets-script tests plus Ansible lint; prove `op user get --me`, an in-scope read, an agent-vault item create/delete exercise, and denial outside the vault; regenerate `.env` non-interactively at mode `0600`; show unattended GitHub SSH auth, the symmetric NFS path from both hosts, Docker daemon reachability, a disposable container, and a bind mount under the symmetric path.

- [ ] Phase 4: Install Amp and commoditize directory runners
  - Goal: Provide the resident ansiblonomicon runner and the ticket 11 arbitrary-directory runner surface through one supervised, narrowly authenticated mechanism.
  - Files: a new `ansible/roles/amp/`, Amp refs/config files, systemd unit templates, a thin runner CLI, tests, the pod042 provisioning skill, and ticket 11.
  - Work: Claim ticket 11; install Amp through Ansible with auto-update enabled; build a systemd runner template and `start`/`stop`/`list`/`logs` CLI with deterministic per-directory identities; make the persistent ansiblonomicon checkout an enabled instance using `--no-tui --remote-control-terminal`; inject only `AMP_API_KEY` through `op run` plus systemd credentials, explicitly removing both service-account variables before Amp exec.
  - Validation: Run CLI/unit tests and Ansible lint; exercise runner lifecycle in the repo and a disposable second directory; create and steer a remote thread; prove restart recovery and inspect the unit/process environments to show Amp has `AMP_API_KEY` but neither the repository `.env` nor `OP_SERVICE_ACCOUNT_TOKEN{,_FILE}`; close ticket 11 only after the prototype's lifecycle questions are resolved by evidence.

- [ ] Phase 5: Add the bounded self-converge and alert loop
  - Goal: Make pod042 update, converge, verify, repair once, and report independently of the Amp conversational surface.
  - Files: a new `ansible/roles/converge_loop/` with wrapper/verifier/notifier code and systemd units, tests, `.secrets.jsonc`, pod042 configuration/playbook files, and the operations runbook.
  - Work: Fold apt upgrades and the controlled Amp runner restart into the daily persistent timer path; implement fetch/reset of the persistent checkout, secrets-cache refresh, local `poe pod042`, and health verification for required units, Docker-over-SSH, NFS, and disk headroom; persist journald/state/transcripts; implement one 30-minute `amp -x --stream-json` repair per failure fingerprint, re-armed only by acknowledgement or a new commit; with Thurston, locate or create the Discord webhook, store it in the agent vault, and send failure, repair, and repeat-fingerprint reports without exposing its URL.
  - Validation: Run deterministic wrapper/verifier/fingerprint/notifier tests and Ansible lint; manually start the healthy service path; inspect timer persistence, state, journal, transcript permissions, and the next scheduled run; prove a standalone Discord test alert arrives and that stopping the resident runner leaves the notifier usable.

- [ ] Phase 6: Prove unattended recovery and close the build
  - Goal: Meet the build ticket's done bar with destructive-enough real-world evidence, then leave the operational record handoff-safe.
  - Files: `docs/operations/` pod042 runbook, `docs/wayfinding/pod042/tickets/09-build-pod042.md`, and any implementation files corrected by the acceptance exercise.
  - Work: Introduce a reversible converge/health failure through the real systemd entrypoint; observe one repair agent run and its allowed repo/box actions; repeat the identical fingerprint to prove alert-only suppression; acknowledge or change HEAD to prove re-arming; reboot pod042 without intervention and let the enabled services, mounts, resident runner, and timer recover; record concrete evidence and any new decision that extends or contradicts this design.
  - Validation: Show the deliberate failure's journal, fingerprint state, bounded Amp transcript/thread, and received Discord report; show the repeat consumed no second repair; after reboot show VM autostart, SSH, NFS, Docker-over-SSH, Amp runner, converge timer, verify script, and a clean local `poe pod042` converge; run the relevant full lint/test suite and close ticket 09 only when every check passes.
