# Headless Amp capabilities for pod042

Researched and updated 2026-07-24 against Amp's current primary documentation and the locally installed Amp CLI (`0.0.1784924859-g1d9e3d`, released 2026-07-24T20:27:39Z). “Supported” below means documented by Amp, not merely plausible through shell scripting.

## Verdict

Amp is a credible **headless, remotely driven coding-agent runner** for pod042. It has a CLI automation interface, a runner mode that accepts remotely created work on a chosen machine and directory, and web/mobile remote control of live CLI threads. A separate hidden `--headless` thread-actor executor also exists in the shipped CLI, but it is not a public feature and current source gates it to Amp employees (unless its internal `AMP_EXECUTOR=1` override is set); it is not the supported resident-runner mode. Amp is not yet sufficient by itself to be the whole resident-agent system: its documentation does not establish that cloud Automations/schedules can target a particular self-hosted runner, nor does it offer generic push, email, or webhook notification for that runner. The self-management loop needs a system service/timer, an external alert transport, and a deliberately managed static Amp access token.

## 1. Headless and programmatic execution — supported

| Need | Verified Amp behavior | Pod042 consequence |
| --- | --- | --- |
| One-shot/non-interactive work | `amp -x/--execute <prompt>` runs a turn, prints the final assistant message, and exits. Redirecting stdout also enables execute mode. It can receive a prompt or stdin. | Suitable for a systemd timer or a wrapper which captures stdout/stderr and decides how to alert. |
| Machine-readable integration | `--stream-json` with `--execute` emits JSON Lines; `--stream-json-input` accepts JSON Lines messages and stays alive until both stdin closes and the assistant finishes. `steer: true` permits queued interruption. | A local supervisor can drive multi-turn work and retain structured logs without scraping a TUI. |
| Continue a known conversation | `amp threads continue <ID> --execute ...` is documented with streaming JSON. | A timer can resume a deliberate maintenance thread, though that is distinct from Amp's cloud schedule feature. |
| Resident remote runner | `amp --no-tui [--runner-id pod042]` waits in its current directory for remote thread-creation requests. Runners are distinguished by host and working directory; `--remote-control-terminal` exposes a terminal to the web UI. | This is the direct fit for a systemd user service in the repository checkout. Use a stable runner ID and a working directory with narrow, intentional authority. |
| Hidden thread-actor executor | `amp --headless [thread-ID-or-URL]` is omitted from `amp --help`. Local installed-source inspection says it either attaches the local workspace/tools to that specific existing thread or creates a new thread, then stays connected as its executor. Current source also rejects non-Amp-employee users unless `AMP_EXECUTOR=1` is set. | This is not `--no-tui`: it binds an executor to one thread rather than waiting for remote thread creation. It is also not `--execute`, which runs supplied input and exits. Do not use it for pod042: no public documentation, support, or entitlement contract exists. |

The CLI also has local thread listing/search/export and a `usage` command. It is a CLI integration, not a documented SDK or stable public agent API. Do not build the resident control plane around undocumented Amp HTTP endpoints.

## 2. Scheduling and automations — supported, but runner placement is unproven

Amp's new schedule feature is a cloud-side Automation. The documented triggers are a time/cadence (“every weekday at 9” or “check again in ten minutes”), a new Slack message, or a GitHub event. An Automation has a job, trigger, and owner; Puck or a regular thread can create, inspect, update, pause, resume, and delete it. A scheduled job can either:

- start a fresh Amp thread per run; or
- wake the existing thread (“heartbeats”), resuming its saved prompt, complete history, and context.

So a heartbeat's durable transcript/output lands in that same synced Amp thread, visible in Amp's feed/web UI. The job can additionally send its result to Slack when configured in its instructions; Amp's examples include DMing a report, posting to a channel, and pinging when a monitored job stalls. There is no documented filesystem log destination, cron expression schema, CLI schedule subcommand, completion callback, or delivery/retry/SLA in the current manual.

**Load-bearing gap:** the primary schedule/Automation material does not say that an Automation can choose a specific self-hosted `amp --no-tui` runner. It says a job can start a thread or wake an existing one, while the independent runner feature accepts threads created from ampcode.com. The hidden `--headless` executor does not change that conclusion: it can attach to a known thread, but no primary source connects Automations to it, and it is not a supported customer feature. Do not assume cloud scheduling will execute on pod042's checkout until a disposable **public `--no-tui` runner** is tested end-to-end: create an Automation, select/continue a runner-backed thread, confirm its shell command runs on the VM, and verify where failure and completion appear. Until then, use a local systemd timer invoking `amp -x` for self-management work.

## 3. Remote conversation — supported, with an important boundary

Amp Server stores and syncs threads, and the documented remote-control path is: start a CLI thread, open it on ampcode.com on desktop or mobile web, then send messages to continue working. The July 2026 “Agents, Everywhere” release says the web, mobile web, and CLI sidebar can watch and drive active agents. With remote terminal control enabled, the web UI can access the runner terminal.

This means that **continuing a known running pod042 thread from anywhere does come with Amp**. Starting a new remote thread on pod042 also comes with the runner feature after enabling `amp.remoteThreadCreation.enabled` or running `amp --no-tui`.

It is not a general, authenticated “chat with the VM” endpoint. Remote work is represented as Amp threads and is subject to the Amp account/workspace visibility model. A deployment must verify the web UI exposes the intended runner selection, restrict thread visibility (private by default), and decide whether remote terminal control is worth granting. Enabling terminal control materially raises the blast radius; Amp can require a recent passkey-authenticated web session for remote control.

## 4. Notifications — partial; choose a separate alert transport

| Surface | Current support | Fit for unattended pod042 |
| --- | --- | --- |
| Local Amp notification | Completion or user-input-blocked alert; over SSH it is only a terminal bell (also enabled with `AMP_FORCE_BEL`). | No. A headless VM's bell is not an alert to Thurston. |
| Amp web/mobile thread | The thread and its results are remotely readable/controlable. | Useful pull surface, not a documented push notification guarantee. |
| Slack | Supported integration: mention `@Amp` to reach personal Puck; examples show a thread asking Amp to ping a teammate and scheduled work DMing/posting reports. | Viable if Slack is acceptable, but it requires Amp/Slack workspace or personal integration and explicit job instructions. |
| Email, generic webhook, phone push | No first-party Amp notification transport found in the current manual, CLI help, security reference, or July 2026 releases. | Missing. Supply ntfy/Pushover/email/webhook independently. |
| Webhook-triggered work | Amp's durable `createWebhook` event endpoints are documented for **Orbs**, not self-hosted runners. Orb handlers may call external APIs to report results. | Do not treat this as a pod042 runner capability. |

A local wrapper is the safe baseline: persist structured output from `amp -x --stream-json`, classify nonzero exit/failure, and send a deliberately configured external alert. Slack can be the interactive addition, not the only evidence path.

## 5. Unattended authentication — static access token supported; service identity/lifetime unspecified

For scripts and CI, Amp explicitly directs users to set `AMP_API_KEY` to an Amp access token. That is the correct headless authentication mechanism, rather than relying on an interactive browser/session login. The CLI also stores credentials locally when using login; Amp's security reference documents the normal client credential store as `~/.local/share/amp/secrets.json` on Linux/macOS.

Amp documents that a leaked access token can be revoked with `POST https://ampcode.com/api/revoke`; revocation invalidates it and generates a replacement token which must be retrieved from Security Settings. It does **not** document an access-token expiry/TTL, automatic renewal, token scopes, or a service-account/machine identity for a resident runner. The automatic refresh described in the manual applies to OAuth tokens for MCP servers, not Amp's own `AMP_API_KEY`.

**Recommendation:** provision a dedicated Amp account/workspace if possible; inject `AMP_API_KEY` from pod042's secret manager into the systemd service; never put it in git, `AGENTS.md`, or a project `.env`; treat it as a broad credential; and provide a rotation/restart runbook plus monitoring for auth failure. An interactive subscription session is not an unattended-auth strategy.

## 6. Non-interactive updates — supported, but supervise the runner

Amp documents the Linux installer as `curl -fsSL https://ampcode.com/install.sh | bash`, with Homebrew and npm alternatives, and the supported explicit update command is `amp update [--porcelain]`. `amp.updates.mode` defaults to `"auto"`; `"warn"` only notifies and `"disabled"` turns checks off. `AMP_SKIP_UPDATE_CHECK=1` overrides that setting and disables checks. The local installation confirms the installer-managed `~/.amp/bin/amp` layout and a release only hours old at research time, so rapid release cadence is real.

For pod042, choose one owner:

- **Amp auto-update:** leave `amp.updates.mode: "auto"`; record versions and have systemd restart the runner when it exits or after a controlled maintenance window.
- **Host-managed update:** set `"warn"` or `"disabled"`, run `amp update --porcelain` from a systemd timer, log the result, then explicitly restart the runner service.

Amp does not document that a live ordinary `--no-tui` runner re-execs after an update. Its documented “services survive CLI updates” promise is specifically for **Orb** services, so do not generalize it to pod042. The runner needs normal systemd supervision and a tested restart path.

## 7. Authority, MCP, and spend controls

- Amp executes tools without approval by default. `amp.dangerouslyAllowAll` disables legacy confirmations; it is the wrong default for an autonomous infrastructure box. Amp can instead use legacy `amp.permissions`, guarded-file rules, tool allow/deny lists, MCP permissions, and TypeScript policy plugins.
- The repository's existing `chezmoi/dot_config/amp/plugins/permission-gate/` is relevant: it protects Git mutations, destructive removal, PostgreSQL mutations, and work web searches, but when no plugin UI is available it rejects protected actions rather than paging a human. That is safe but means unattended repair must be able to stop and report.
- MCP is supported from settings, CLI, or skills. Workspace MCP servers need explicit approval; globally configured MCP servers do not. Use a minimal allowlist and separate credentials because an MCP tool expands the runner's authority.
- `low`, `medium`, `high`, and `ultra` select speed/capability/cost; `fast` carries a premium. `amp usage` exposes current usage/credit balance and thread pages expose detailed cost. Individual/team usage is pass-through provider cost; Amp documents hard per-user cost controls only as an Enterprise entitlement. There is no documented per-run dollar ceiling, concurrency cap, or local runner spend budget. Bound work with local timers, modes, timeouts, quotas/credit monitoring, and a fail-closed supervisor.
- Threads, user data, and telemetry are stored in Amp's multi-tenant cloud; Amp does not offer self-hosting. The remote convenience is therefore coupled to Amp Server availability and account security.

## Decision for downstream tickets

Use Amp as a **candidate execution and remote-thread plane**, not as the entire resident control plane. Ticket 05 should design a local systemd-supervised loop with explicit logs, limits, and an external failure notifier; it may invoke `amp -x` and later adopt a verified runner-targeted Automation. Do not build on hidden `--headless`; its specific-thread actor harness does not close the Automation-to-runner gap. Ticket 06 can rely on Amp web/mobile for active-thread conversation and optionally Slack, but must choose a separate alert transport and decide whether to expose remote terminal control. Both tickets must validate runner-targeted scheduling and static-token rotation before treating headless Amp as operationally sufficient.

## Primary sources

All links checked 2026-07-24.

- [Amp Owner’s Manual](https://ampcode.com/manual) — installation, CLI execute/streaming modes, runners, remote control, Slack, notification setting, MCP, permissions, `AMP_API_KEY`, update mode, and pricing.
- [Agents, Anywhere — 2026-07-08](https://ampcode.com/news/agents-anywhere) — `amp --no-tui` runner mode and host/directory identity; its phrase “headless mode” refers to `--no-tui`, not the hidden `--headless` flag.
- [Putting an Agent in an Orb — 2026-07-02](https://ampcode.com/notes/putting-an-agent-in-an-orb) — likely source of the “headless remote machine” wording; it describes Amp-hosted Orbs and does not document `amp --headless`.
- [Agents, Everywhere — 2026-06-04](https://ampcode.com/news/agents-everywhere) — web/mobile/CLI control surfaces and durable agent execution.
- [Right on Schedule — 2026-07-21](https://ampcode.com/news/schedule) — saved-prompt/context heartbeats and Slack reporting examples.
- [Automations — 2026-07-13](https://ampcode.com/news/automations) — schedule, Slack, and GitHub trigger model; fresh-thread versus existing-thread runs. The announcement currently redirects to the schedule update, so its runner-placement details should be validated in product before implementation.
- [Amp Is Now In Slack — 2026-07-20](https://ampcode.com/news/slack-integration) — Slack setup, Puck, and thread-driven teammate notification.
- [Event Driven Orbs — 2026-07-23](https://ampcode.com/news/event-driven-orbs) — event webhooks are an Orb capability, plus external reporting from an Orb plugin.
- [Amp Security Reference](https://ampcode.com/security) — cloud architecture, credential storage, remote-control passkey option, updater download source, and access-token revocation.
- Local evidence: `amp --help`, `amp update --help`, `amp version`, and installed source at `~/.amp/package/dist/main.js` on 2026-07-24. The public help exposes runner, execute, JSON streaming, remote-terminal, access-token, permissions, MCP, usage, and update interfaces; the source alone exposes hidden `--headless [thread]`, its single-thread executor behavior, and its employee/`AMP_EXECUTOR=1` gate.
