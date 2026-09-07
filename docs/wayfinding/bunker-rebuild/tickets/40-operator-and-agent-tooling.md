---
status: closed
type: implementation
blocked-by: [31, 33]
---

# Operator and agent tooling

## Question

Decide which workstation-like and agent-facing tools belong on the NAS host itself: mise-managed runtimes, uv and language tools, chezmoi, shell environment, Neovim, tmux, sessions, Herdr, terminal-theme mirroring, Pi and other agent harness resources. Separate host operations needs from conveniences that belong only inside the durable agent instance.

Audit the old playbook package list and roles without preserving them by inertia.

## Decisions

- Bootstrap owns software, accounts, and service lifecycle. Chezmoi owns user configuration.
- `operator/mise.toml` is the global tool inventory. The operator capability declares Debian packages and named mise tasks for tools, sessions, dotfiles, and tmux. Do not hide that inventory in setup scripts.
- Neovim is the editor on every host. Retire VS Code editor routing and Claude Code Tools.
- T3 is an operator-wide service for multiple projects, running from the operator's home through the vendor's service lifecycle. Amp's durable remote-terminal runner is repo-specific.
- Both services run as `thurstonsand`, with attended enrollment and linger for persistence. Authentication and a working remote session must be demonstrated, not inferred from systemd activity.

## Implementation state

Operator tools and vendor-installed agents are installed on pod042. Codex, Claude, Amp and T3 enrollment are complete; T3's vendor boot unit is retained. Native harness reconciliation now reuses the shared catalogue and resolver for Claude, Amp, Codex, OpenCode and Pi, with Amp's hosted catalogue policy preserved. Deployment and remote verification are complete: Amp returned `READY` through a cloud-targeted NAS thread, and T3 served authenticated provider/skill RPC over its managed public endpoint. Amp terminal commands still require the user's normal account passkey assertion; that protection remains intact. Both services remained active after the verification SSH session closed. Actual reboot testing stays deferred to an attended window.

Evidence: [physical operator and remote-agent verification](../artifacts/operator-2026-09-06/README.md).

See [operator setup](../../../../bootstrap/targets/pod042/operator/README.md), [harness resources](../../../../bootstrap/targets/pod042/agent-harness/README.md), and [remote enrollment](../../../../bootstrap/targets/pod042/remote-development/README.md).

## Resolution

Closed 2026-09-06. Pod042 now has the accepted operator environment, all five native harness catalogues, and persistent authenticated Amp and T3 remote-development services. The base capability supplies only the packages and account state these capabilities consume. Broader package, upgrade, locale, time, reboot, and retirement policy remains a decision in [Base host desired state](32-base-host-desired-state.md), but it did not block completing operator and agent tooling; that false dependency was removed when this ticket closed.
