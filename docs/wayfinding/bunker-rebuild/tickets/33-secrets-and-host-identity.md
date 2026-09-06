---
status: closed
type: grilling
blocked-by: [31]
---

# Secrets and host identity

## Question

Decide pod042's machine identity and secret-delivery model under native mise: hostname and DNS facts, SSH host and operator keys, 1Password service-account bootstrap, secret material allowed on disk, systemd credential delivery, rotation, remote-reconcile authentication, and recovery when the workstation or 1Password is unavailable.

Audit the prior `op_service_account` behavior rather than translating it. Close with explicit ownership and failure behavior; then create a separate implementation ticket.

## Design and implementation

The user approved [design 25](../../../designs/25-fnox-secret-delivery.md) and its execution plan. This machine's target is `macos`; `omarchy` is the next planned target, to be registered when its hostname and credentials are known. [Ticket 43](43-fnox-secret-delivery.md) holds the separate implementation work and completion evidence.

## Grill progress

Round 1 selects fnox as mise's provider boundary rather than recreating the Ansible `op` launcher. The retained 1Password service-account token is readable by `thurstonsand` and root. Secret values remain remote except for narrowly rendered service credential files; pod042 does not receive a broad repository `.env`. Missing 1Password access fails before mutation while existing rendered credentials and running services remain intact. Hark failure delivery lands before storage maintenance, while Healthchecks registration lands with the timers it supervises. Blank-host token installation is a separate attended command because it should be rare, explicit recovery work rather than permanent complexity in first access.

Secret declarations split into root-level `fnox.toml` plus explicit root-level host profile files. A secret moves to the shared list only when at least two hosts consume it; host-only authority remains in that host's profile, including the constrained work-machine profile. The migration replaces `.secrets.jsonc` and every consumer in one controlled change rather than creating a split-brain transition. Its final work-machine step emits a one-time instruction to review and update the gitignored files catalogued by `README.work.md`.

The attended identity-bootstrap command installs pinned fnox and 1Password CLI prerequisites, streams the retained token from the operator's authenticated workstation into its final mode-0600 path, and proves that a host-profile secret resolves. Re-running the command rotates the installed token to the declared 1Password value.

Round 2 chooses one effective secret set per host, not operation profiles or shared consumer groups. The broader child environment and dependency on all selected host credentials are accepted in exchange for simpler declarations. Root shared references and host-only additions remain the ownership model. Host selection uses exact known hostnames and rejects unknown hosts at secret-consuming entrypoints, without blocking unrelated bootstrap or checks.

Chezmoi uses its native generic `secret` command integration backed by fnox, with per-invocation lookup caching and no duplicate SecretRefs or command alias. Direct chezmoi retains native partial-apply behavior if a later lookup fails. Full reconciliation preflights its effective host secrets before mutation. Work retains explicitly declared access to both personal and corporate accounts; a host profile is not an account restriction.

Migrate Orb secret access to fnox rather than removing the runner's ability to use secrets. Its supplied service identity authenticates fnox; an explicit runner profile replaces hostname guessing for ephemeral runners. Ordinary runner dependency bootstrap does not require a token, and secret-consuming commands resolve through fnox without generating `.env`. Remove the old `.agents/resume` token-gated bootstrap and `scripts/init-secrets.py` Orb special case as part of the atomic consumer switch.

Remove legacy secret declarations, adapters, commands and current documentation references rather than retaining an inactive legacy profile or compatibility fallback. Verify consumers before removal so active ones migrate instead of silently breaking. Preserve historical evidence as history, not executable recovery paths. Do not delete 1Password items as part of repository cleanup.
