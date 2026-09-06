---
status: open
type: implementation
blocked-by: [31, 32, 33]
---

# Operator and agent tooling

## Question

Decide which workstation-like and agent-facing tools belong on the NAS host itself: mise-managed runtimes, uv and language tools, chezmoi, shell environment, Neovim, tmux, sessions, shpool, terminal-theme mirroring, Pi and other agent harness resources. Separate host operations needs from conveniences that belong only inside the durable agent instance.

Audit the old playbook package list and roles without preserving them by inertia.

## Decisions

- Bootstrap owns software, accounts, and service lifecycle. Chezmoi owns user configuration.
- `operator/mise.toml` is the global tool inventory. The operator capability declares Debian packages and named mise tasks for tools, sessions, dotfiles, and tmux. Do not hide that inventory in setup scripts.
- Neovim is the editor on every host. Retire VS Code editor routing and Claude Code Tools.
- T3 is an operator-wide service for multiple projects, running from the operator's home through the vendor's service lifecycle. Amp's durable remote-terminal runner is repo-specific.
- Both services run as `thurstonsand`, with attended enrollment and linger for persistence. Authentication and a working remote session must be demonstrated, not inferred from systemd activity.

## Implementation state

Native operator and remote-development declarations are implemented locally. Template rendering, task ordering, and static checks pass. The first NAS deployment, provider/Amp/T3 enrollment, and disconnect-persistence checks remain pending. Harness-managed skill catalogues remain a separate migration item.

See [operator setup](../../../../bootstrap/targets/pod042/operator/README.md) and [remote enrollment](../../../../bootstrap/targets/pod042/remote-development/README.md).
