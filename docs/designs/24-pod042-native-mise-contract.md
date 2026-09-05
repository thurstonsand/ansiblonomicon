# pod042 native mise operating contract

## Status

Accepted

## Decision Summary

pod042 uses mise's native bootstrap resources as its host reconciliation engine, with one target declaration shared by local and SSH-driven runs. A small, VM-proven landing zone is enough to erase the TrueNAS boot SSD; storage and services follow as separately approved host capabilities while the ZFS pools remain untouched.

The key tradeoff is downtime for momentum. Full service parity does not block the OS replacement, but manageability does: first access, key-only SSH, sudo, a persistent checkout, system mise, reboot recovery, planning, and local/remote equivalence must work from blank Debian before TrueNAS disappears.

## Problem Statement / Background

The existing `mise pod042` command still runs the old Ansible playbook. That playbook is useful migration evidence, but the fresh Debian host must never execute it. Ticket 20 proved that mise could reproduce an Ansible segment, but only by adding a 343-line shell reconciliation runtime. Since that trial, mise gained native declarative bootstrap resources for accounts, packages, files, services, firewall, compose projects, repositories, dotfiles, systemd, secrets, status, planning, and SSH-driven remote application. The live UDMP target proves that newer shape on real hardware.

The immediate operational scenario is narrower than rebuilding every NAS service. A stock Debian installer replaces TrueNAS on one 448 GB boot SSD. The data-bearing ZFS members must not be selected or imported during installation. After first boot, a workstation must turn a password-accessible Debian host into a managed, key-only host; after reboot, both the workstation and pod042 itself must reconcile the same declaration cleanly. Once that path survives destruction and recreation in a VM, the boot SSD can be wiped without waiting for Docker, SMB, backup, or agent-platform parity.

## Goals

- Give pod042 one native mise declaration with equivalent local and remote behavior.
- Establish a small, destructive-testable landing zone before erasing TrueNAS.
- Make full and capability-scoped reconciliation direct, serial, idempotent, inspectable, and fail-fast.
- Keep the persistent checkout synchronized without overwriting local work or applying an unpushed revision as durable state.
- Preserve `.secrets.jsonc` and 1Password as the secret source while limiting pod042's generated cache to declared host keys.
- Admit custom reconciliation code only when a concrete resource exceeds native mise.

## Non-Goals

- Automating the Debian installer or encoding installer choices as mise resources.
- Importing or changing the real ZFS pools as part of the landing zone.
- Restoring applications, shares, backup, alerting, containers, or agent workloads before the boot-SSD wipe.
- Recreating Ansible tags, role defaults, inventory precedence, or its reporting layer.
- Solving permanent pod042 addressing, bridges, firewall, WOL, or remote KVM access in this contract.

## Exposed Shape

### Operator CLI

- `mise pod042` converges all pod042 host capabilities.
- `mise pod042 <capability>` converges one named config root. Initial names follow the desired-state boundaries: `base`, then later `identity`, `network`, `storage`, `sharing`, `containers`, `services`, `backup`, and `agents`.
- `mise pod042 --check` reads actual state and reports changes without mutation.
- `mise pod042 <capability> --check` checks only that capability.
- `mise pod042 --update-mise` deliberately updates the system-wide target binary before reconciliation.

The command inspects the local hostname. On `pod042`, it runs the persistent target locally. Elsewhere, it validates Git state, safely fast-forwards the remote checkout, then drives the same target over SSH. A precondition failure returns nonzero before host mutation and names the violated condition.

### Bootstrap target

`bootstrap/targets/pod042/` is the only desired-state declaration. Its root composes concrete capability config roots and pins serial execution. Local execution reads it from `/home/thurstonsand/code/ansiblonomicon`; initial remote execution may stage it before that checkout exists.

Each capability owns a coherent outcome, its files, and any custom status/apply implementation. It does not carry speculative defaults or exported environment interfaces. Shared facts move to the target root only after more than one capability consumes them.

A target-level `.miseremove` declares retired paths. Full check and converge process it; capability-only runs may defer unrelated removals until the next full run.

### First-access workflow

The stock Debian installer creates user `thurstonsand`, obtains Bunker DHCP, and installs OpenSSH. The cutover wizard:

1. prompts for the install password without echo;
2. creates or updates a `pod042` Login item in the `agent` vault using JSON over standard input;
3. uses the password once to install the existing operator SSH key;
4. invokes the native remote bootstrap;
5. verifies a new key-only SSH connection before password authentication is disabled.

The password never enters command arguments, `.env`, or cutover state. It remains in 1Password for physical or KVM console recovery. Managed `thurstonsand` retains full passwordless sudo.

### Git boundary

The persistent public checkout is `/home/thurstonsand/code/ansiblonomicon`, owned by `thurstonsand`. Default remote reconciliation requires:

- clean workstation and host checkouts;
- the same checked-out branch on each;
- workstation `HEAD` equal to its upstream;
- the host revision either equal to or an ancestor of that exact commit.

The host fetches and fast-forwards only to that commit. The driver never switches branches, rebases, resets, merges divergent history, or pulls an unspecified newer revision. First bootstrap clones the default branch. An uncommitted development deployment, if later needed, requires a separate explicit interface.

### Secrets boundary

`.secrets.jsonc` remains the committed SecretRef index. Ticket 33 installs the existing `agent` service-account token and defines the pod042 key allowlist. The host resolves only allowed keys into its mode-0600 `.env` cache. Secret regeneration completes before a fresh mise process starts, avoiding the current first-process stale environment behavior.

Secret values may cross only into declared secret inputs or mode-0600 outputs. Plans, diffs, commands, logs, errors, staging archives, and normal files must not contain them. Missing required secrets fail before mutation. The landing zone itself does not require service secrets.

### Custom resource contract

Native mise owns every resource it can express. A custom mutating resource normally provides real-state status, non-mutating plan output, idempotent apply, nonzero failure, secret-safe output, and focused tests. A per-resource comment may waive plan behavior when planning has no useful meaning or costs more than the safety it adds; status, idempotency, failure propagation, secret safety, and tests remain mandatory.

## Call Stacks and Data Flow

### First remote bootstrap

```txt
stock Debian + DHCP + password SSH
  -> cutover wizard hidden password prompt
  -> 1Password Login item via JSON stdin
  -> ssh-copy-id as thurstonsand
  -> mise pod042 bootstrap against DHCP address
    -> stage bootstrap/targets/pod042
    -> install pinned target-architecture mise
    -> native bootstrap host guard
    -> accounts and sudo
    -> packages
    -> files and SSH hardening
    -> services
    -> public repo clone
  -> open a second key-only SSH connection
  -> reboot
  -> reconnect and run local check from ~/code/ansiblonomicon
```

### Normal workstation reconcile

```txt
mise pod042 [capability] [--check]
  -> detect workstation hostname
  -> validate local checkout is clean and pushed
  -> SSH to pod042
  -> validate remote checkout is clean and on the same branch
  -> fetch and fast-forward remote to exact local HEAD
  -> invoke target/capability from persistent checkout
    -> hostname guard
    -> native bootstrap plan or apply
    -> optional tested custom resource plan or apply
  -> preserve native exit status and output
```

### Local reconcile

```txt
mise pod042 [capability] [--check]
  -> detect hostname pod042
  -> use current persistent checkout without pulling
  -> hostname guard
  -> native bootstrap plan or apply
  -> preserve native exit status and output
```

### Secret resolution after ticket 33

```txt
.secrets.jsonc
  -> pod042 hostname allowlist
  -> op inject using local agent service-account credential
  -> mode-0600 .env temporary replacement
  -> exec fresh mise process
  -> declared native secret inputs
  -> mode-0600 service files or systemd credentials
```

## Design Decisions

### 1. The landing zone gates the wipe

Full replacement parity would keep TrueNAS running longer without making the boot-SSD operation safer. The landing zone proves the recovery control path and deliberately stops before the real pools. Service downtime is accepted; unmanaged recovery is not.

### 2. Native mise is the reconciliation engine

Current mise already owns the common privileged resources and supplies status, planning, notifications, fixed phase ordering, secret templates, and remote bootstrap. Recreating those in shell would preserve the trial's largest liability. The trial remains a library of evidence and candidate primitives for specific gaps.

### 3. One target supports two transports

Local and remote commands may differ in transport but not desired state. The remote path stages the target for first bootstrap; the persistent checkout then gives pod042 the same local declaration. A second implementation would drift precisely when recovery needs predictability.

### 4. Capabilities replace tags

A capability is an ownership boundary, not a cross-cutting task label. Narrow names such as `storage` and `containers` say what state changes. Broad `system` and tool-named `docker` groups can be added only after repeated operator use justifies them.

### 5. Concrete declarations precede reuse

This target configures one known host. Role-style defaults, inheritance, and interface files would import mise's weakest precedence behavior before a second consumer exists. Direct resources are easier to review and fail closer to their declaration.

### 6. Execution is serial and fail-fast

The trial demonstrated dpkg-lock and API races under mise's parallel default. The target pins `jobs = 1`; operators do not carry that safety property in memory. The first failure stops later mutation and returns nonzero. Native output remains the report until it proves insufficient.

### 7. Git synchronization is conservative but convenient

A pushed commit followed by `mise pod042` safely deploys that exact commit. Requiring clean, same-branch, upstream-equal state prevents automatic synchronization from consuming recovery edits, mixing staged content with another persistent revision, or silently choosing main over the caller's branch.

### 8. Passwordless sudo is an explicit trust grant

pod042 has one human administrator and later hosts root-equivalent automation. Command-scoped sudo would mostly enumerate shell-capable routes back to root while making every capability edit sudo policy. The SSH key is therefore treated as a host-administrator credential, and SSH password authentication is disabled after key verification.

### 9. SecretRefs remain central, host caches become scoped

The repo does not need a second secret declaration. It does need a pod042 allowlist because the current hostname filter otherwise resolves nearly every agent-vault key. The service account supplies access; it does not decide which credentials this host should retain.

### 10. The installer remains out of band

The KVM already supplies reliable video, HID, and virtual media. Automating installer screens adds a fragile destructive program at the exact point where human confirmation has value. The wizard owns transitions and evidence around the installer, not the installer itself.

## Edge Cases & Failure Modes

- **Workstation has staged, unstaged, untracked, or unpushed changes:** remote reconciliation aborts before fetch or host mutation.
- **Host checkout contains an emergency edit:** reconciliation aborts and preserves it. The operator decides how to commit or remove it.
- **Branches differ or histories diverge:** reconciliation aborts; it never switches or resets either checkout.
- **Host has no checkout yet:** initial remote bootstrap stages the target and clones the public default branch.
- **Target mise is missing or too old:** first bootstrap installs the target architecture; later runs require explicit `--update-mise` when the pinned minimum advances.
- **SSH hardening would sever access:** bootstrap keeps the current session, validates sshd configuration, and proves a second key-only connection before declaring the transition complete.
- **Reconcile runs on the wrong host:** the hostname guard fails before mutation.
- **A native resource differs in check mode:** native plan reports it without applying it and returns the documented detailed status where used.
- **A custom task fails after earlier changes:** it exits nonzero, later work does not run, and a rerun safely resumes convergence.
- **A required secret is unavailable:** secret preflight fails before mutation; an existing cache may support explicitly allowed offline reconciliation after ticket 33 defines that policy.
- **A secret renderer fails:** output contains no secret value; the VM gauntlet searches all captured output and staging for a sentinel.
- **A capability-only run leaves an unrelated retired path:** the path remains until a full reconcile. This is deliberate and visible, not an `always` behavior mise does not possess.
- **TrueNAS pools were not exported cleanly:** installation stops. The accepted backup refresh waiver does not waive clean pool export or disk identity checks.

## Alternatives

### Adopt the trial shell runtime

- **Status:** Rejected
- **Decision:** Native mise now supplies the common reconciliation behavior, while the trial runtime adds 343 untested privileged lines and a second reporting model.
- **Discussion:** Individual primitives remain useful when a real resource gap appears. They enter under the custom resource contract with tests.

### Require ZFS or service parity before wiping

- **Status:** Rejected
- **Decision:** The data pools are separate from the erased SSD, extended downtime is accepted, and the landing zone proves the actual recovery prerequisite.
- **Discussion:** Storage still receives its own desired-state signoff and disposable-pool tests before touching the real pools.

### Automate Debian installation

- **Status:** Rejected
- **Decision:** Stock netinst through the proven KVM is simpler and safer than maintaining screen automation or a custom ISO for one host.
- **Discussion:** The cutover wizard still records the target disk and manages the first credential transition.

### Broad `system` and `docker` partial runs

- **Status:** Rejected
- **Decision:** They combine unrelated ownership boundaries and make a partial run's effects difficult to predict.
- **Discussion:** Group aliases remain available if repeated operator behavior later earns them.

### Send the complete `.env` to pod042

- **Status:** Rejected
- **Decision:** The service account's vault access does not justify caching unrelated Cloudflare, UniFi, laptop, and application credentials on the host.
- **Discussion:** `.secrets.jsonc` and the existing resolver remain; ticket 33 adds host selection rather than inventing another source.

## Implementation Plan

- [x] Phase 1: Native target and guarded driver
  - Goal: Add the shared pod042 target and replace the Ansible-backed public entrypoint without exposing an incomplete first-access flow.
  - Files: `bootstrap/mise.toml`, `bootstrap/targets/pod042/`, `mise.toml`, focused tests under `tests/`.
  - Work: Add the pod042 inventory and target skeleton; pin serial execution; implement hostname guard, base capability selection, local/remote dispatch, exact guarded Git synchronization, native check mapping, and explicit mise update. Use native resources only.
  - Validation: Parser/config checks, unit tests for dispatch and every Git refusal/fast-forward path, shell lint where applicable, and a harmless local wrong-host rejection.

- [x] Phase 2: First-access and retirement workflow
  - Goal: Turn stock password-accessible Debian into the landing zone without exposing credentials or losing SSH.
  - Files: `docs/wayfinding/bunker-rebuild/scripts/bringup.sh` or a replacement cutover script, `bootstrap/targets/pod042/base/`, target `.miseremove`, tests.
  - Work: Add hidden password capture and JSON-stdin 1Password item create/update; install the operator key; declaratively own `thurstonsand`, passwordless sudo, key-only sshd, required base packages, system mise, and the user-owned public checkout; verify a second SSH connection before closing password access; implement validated retirement planning/apply only if native mise cannot express it.
  - Validation: Secret-sentinel tests, mocked command-flow tests, native bootstrap plan, shell lint, and an isolated SSH transition smoke test.

- [x] Phase 3: Destructive landing-zone VM gauntlet
  - Goal: Produce reproducible evidence that blank Debian can reach and retain managed state through both transports.
  - Files: `docs/wayfinding/bunker-rebuild/prototypes/native-mise/` or equivalent test harness, ticket 42 evidence.
  - Work: Script VM creation/reset; exercise first remote converge, reboot, guarded checkout update, remote/local no-op, induced drift plan and repair, hostname rejection, fail-fast behavior, and sentinel searches; destroy and recreate once and repeat the bootstrap proof.
  - Validation: One command runs the gauntlet from blank VM to final clean local plan with no Ansible invocation.

- [x] Phase 4: Cutover gate and runbook correction
  - Goal: Make the remaining path from TrueNAS to stock Debian explicit and executable.
  - Files: `docs/wayfinding/bunker-rebuild/tickets/09-cutover-runbook.md`, cutover scripts, ticket 31 and landing-zone implementation ticket.
  - Work: Record the accepted backup-refresh waiver; restore temporary TrueNAS DHCP/SSH; identify the boot SSD by model and serial; replace stale move-day and Ansible stages; require service stop, final snapshots, explicit clean export of both pools, KVM/ISO readiness, and installer selection of only the boot SSD.
  - Validation: Dry-run every non-destructive stage, inspect the rendered operator flow, then stop at the final irreversible confirmation until the live cutover begins.
