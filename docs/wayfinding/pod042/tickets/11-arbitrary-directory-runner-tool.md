---
status: closed
type: prototype
blocked-by: []
---

# Arbitrary-directory Amp runner tool

## Question

An Amp runner (`amp --no-tui --remote-control-terminal`) binds to a single working directory — confirmed by hands-on testing. Build a cheap concrete tool that makes runners a per-directory commodity: clone a repo, point the tool at it, get a persistent headless runner there. Likely shape: a systemd user template unit (`amp-runner@.service` with systemd-escaped path) plus a thin CLI wrapper (`start <dir>` / `stop` / `list` / `logs`). Decisions to force via the prototype: runner-id naming per directory, env injection (`AMP_API_KEY` via the secrets pattern), restart policy, lifecycle/GC of forgotten runners, and how these ad-hoc runners relate to the converge-managed resident runner in the repo checkout (same mechanism, or is the resident just `start ~/ansiblonomicon` made permanent?). Prototype can be built and exercised on any machine with Amp; productionizing lands via [Playbook and VM provisioning design](07-playbook-and-vm-design.md).

## Resolution

Closed 2026-08-19: unresolved idea. Superseded platform (bunker-rebuild ticket 07); re-charter against pascal/incus if the need resurfaces.
