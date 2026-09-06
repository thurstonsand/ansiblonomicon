---
status: open
type: grilling
blocked-by: [31, 32, 33]
---

# Operator and agent tooling

## Question

Decide which workstation-like and agent-facing tools belong on the NAS host itself: mise-managed runtimes, uv and language tools, chezmoi, shell environment, Neovim, tmux, sessions, shpool, terminal-theme mirroring, Pi and other agent harness resources. Separate host operations needs from conveniences that belong only inside the durable agent instance.

Audit the old playbook package list and roles without preserving them by inertia. Close with an explicit install and ownership inventory; then create a separate implementation ticket.
