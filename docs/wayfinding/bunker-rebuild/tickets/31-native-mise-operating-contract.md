---
status: closed
type: grilling
blocked-by: [20]
---

# Native mise operating contract

## Question

Define the common contract every pod042 capability must use before migration decisions fan out. Native mise is decided; the remaining question is how to make it safe enough to own a host.

Settle:

- one declaration that supports both local self-reconciliation and remote SSH-driven reconciliation
- initial bootstrap before the repository, secrets, or a system-wide mise binary exists
- unit boundaries and dependency ordering under monorepo config roots
- idempotency, check mode, diffs, change reporting, handlers, partial runs, failure propagation, and retirement
- structured host facts and defaults without inverted precedence
- secret-safe rendering that cannot dump the process environment on an error
- whether to adopt, replace, or reduce the trial's custom reconciliation runtime
- test seams and the VM gauntlet required before the first bare-metal converge

The old Ansible playbook is evidence and an audit list, not a parity target.

## Progress

2026-09-05, grill rounds 1–3: the wipe gate is a **landing zone**, not full service parity. Before erasing TrueNAS, a fresh Debian VM must prove first SSH access, native mise remote bootstrap, reboot recovery, and an equivalent clean local reconcile. The pools remain untouched until the separately approved ZFS capability is ready. Native mise bootstrap resources are the reconciliation engine; custom code enters only for a demonstrated gap, one tested resource at a time rather than by adopting the trial's 343-line runtime.

The Debian installer creates `thurstonsand`; a hidden wizard prompt writes that password directly to a retained `pod042` Login item in the `agent` vault, then uses it once to establish the existing operator key. Managed SSH becomes key-only while the retained password remains available for physical or KVM console recovery. `thurstonsand` keeps full passwordless sudo. The public repo checkout lives at `/home/thurstonsand/code/ansiblonomicon` and remains user-owned.

`mise pod042` auto-selects transport: it runs locally on hostname `pod042` and otherwise stages the same `bootstrap/targets/pod042` declaration over SSH. Units use concrete pod042 resources rather than speculative role defaults. Capability config environments replace tags as the partial-reconciliation boundary; raw leaf tasks are not operator entrypoints. Native absent-state resources perform declarative retirement when their owning capability runs.

A custom mutating resource normally must inspect actual state, provide non-mutating plan output, apply idempotently, fail nonzero, conceal secrets, and carry focused tests. A documented exception may omit plan behavior when a dry run has no meaning or its implementation cost outweighs its safety value; the exception is explicit at the resource rather than weakening the contract globally.

Grill rounds 4–6 settled the remaining operations. Partial runs use narrow capability names: `mise pod042` converges all state, while `mise pod042 storage` selects one config environment; broad `system` and tool-named `docker` groups are withheld until actual use earns them. The target pins `jobs = 1`, stops on the first failure, and relies on native bootstrap output and exit status rather than porting the trial ledger. It guards only the `pod042` hostname; capability-specific code owns any stronger hardware or pool assertions. The system-wide mise minimum is pinned and updated only by `mise pod042 --update-mise`.

The persistent checkout updates by an exact guarded fast-forward. Both workstation and host checkouts must be clean and on the same branch, workstation `HEAD` must equal its upstream, and the host may only fast-forward to that exact commit. Any dirty, unpushed, ahead, or diverged state fails before reconciliation. Retired paths use mise's native `state = "absent"` resources rather than a separate manifest.

`.secrets.jsonc` remains the committed SecretRef source. The existing `agent` service account resolves values locally on pod042 after ticket 33 installs its token, and a pod042 allowlist limits the generated mode-0600 `.env` cache to host-required keys. This narrowing is new work: the current hostname filter excludes laptop/work-only keys but otherwise resolves most agent-vault secrets. Secret regeneration explicitly precedes a fresh mise process so first-run values are visible. Values remain absent from plans, diffs, commands, logs, and errors.

The stock Debian installer remains an out-of-band KVM procedure rather than mise state. It creates `thurstonsand`, uses DHCP on the existing Bunker port, and installs OpenSSH. The cutover wizard handles the hidden password-to-1Password and password-to-key transition, then invokes native mise. The final network declaration stays with ticket 36.

Before TrueNAS may be erased, a destructive Debian 13 amd64 VM gauntlet must start without mise, repo, or secrets and prove: first remote convergence; reboot and SSH reconnection; exact guarded checkout update; clean remote and local reruns with matching state; accurate non-mutating drift reporting and repair; serial fail-fast behavior; hostname rejection; and absence of a sentinel secret from output and staging. Destroy and recreate the VM once, then repeat first remote convergence and local no-op. Full service or ZFS parity is not part of this landing-zone gate.

## Resolution

[Design 24](../../../designs/24-pod042-native-mise-contract.md) records the accepted contract and handoff-safe plan. The first implementation slice is [ticket 42](42-pod042-landing-zone.md). Native bootstrap resources own the common state, `mise pod042 [capability]` shares one target between local and remote transports, and the focused landing-zone VM gauntlet rather than full service parity gates erasing TrueNAS.
