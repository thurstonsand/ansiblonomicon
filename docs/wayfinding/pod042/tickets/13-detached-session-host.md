---
status: closed
type: grilling
blocked-by:
  - 11
---

# Detached session host for pod042

## Question

Pod042 needs a durable, reconnectable place to run agent-driven work after the initiating terminal or remote-control session has gone away. Decide the detached-session mechanism: conventional `tmux`, a purpose-built tool such as Herdr, or another viable option. Resolve the operator and agent workflow — creating, naming, reattaching to, inspecting, and terminating work; preserving logs and context; surviving SSH/Amp disconnections and reboots; access control; and how it composes with the per-directory Amp runners from [Arbitrary-directory Amp runner tool](11-arbitrary-directory-runner-tool.md). Deliver the deployment contract for pod042, including whether the selected mechanism replaces or complements its resident runner.

## Resolution

Closed 2026-08-19: unresolved idea. Superseded platform (bunker-rebuild ticket 07); re-charter against pascal/incus if the need resurfaces.
