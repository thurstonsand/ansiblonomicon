# Fnox secret delivery

## Status

Accepted

## Decision Summary

Replace the repository's `.secrets.jsonc` and generated `.env` with fnox-backed 1Password references in one controlled consumer switch. Keep shared declarations in root `fnox.toml`, host-only declarations in root host profile files, and one effective secret set per host. Accept broader injection and availability dependencies within that host set rather than building operation profiles; direct chezmoi uses its native `secret` integration.

This replaces the secret-cache portion of [the pod042 native mise contract](24-pod042-native-mise-contract.md), not its native-resource, serial execution, Git deployment, or destructive-operation safeguards. Design discussion belongs to [ticket 33](../wayfinding/bunker-rebuild/tickets/33-secrets-and-host-identity.md); implementation belongs to [ticket 43](../wayfinding/bunker-rebuild/tickets/43-fnox-secret-delivery.md).

## Problem Statement / Background

The current resolver selects a few machine-specific values but otherwise reads almost the entire secret index, writes a repository `.env`, and generates two Worker `.dev.vars` files. Mise loads that cache into ordinary shells. Its enter hook can create the file only after the invoking process has already resolved its environment, so the first reconciliation can receive empty or stale values.

Chezmoi duplicates raw references in an environment-first helper and SSH templates. Worker deploy scripts read generated files rather than current provider values. Agent/MCP processes and uncommitted work-machine templates depend on the same shell cache. Replacing only pod042 would leave two authoritative secret systems and make failures harder to diagnose.

Fresh Debian pod042 needs unattended identity and external Hark delivery before storage maintenance. Its services must continue using their rendered credentials when 1Password is unavailable, but reconciliation must fail rather than silently use an old general-purpose cache.

## Goals

- One committed authority for named text-secret references, with explicit provider accounts and predictable host selection.
- Plain `chezmoi apply` and mise-driven consumers work without command aliases or duplicate SecretRefs.
- Ordinary dependency bootstrap and shell entry need no secrets.
- Reconciliation resolves required credentials before resource mutation and preserves existing service credentials on provider failure.
- Orb uses the same system without pretending an ephemeral runner is a registered physical host.
- Remove obsolete secret paths rather than keeping dormant profiles or compatibility fallbacks.

## Non-Goals

- Operation-level least-privilege profiles. Each host has one effective set, intentionally.
- Replacing 1Password item creation, SSH-agent operations, or binary document download with text-secret lookup.
- Moving existing GitHub Actions credentials into 1Password or giving CI pod042's service identity.
- Deleting 1Password items, recreating ZFS pools, enabling scheduled maintenance, or reviving retired TrueNAS/OpenClaw hosts.
- Rewriting historical evidence to imply it used fnox.

## Exposed Shape

### Declarations and identity

`fnox.toml` owns shared references consumed by at least two supported execution environments. `fnox.macos.toml`, `fnox.work.toml`, `fnox.pod042.toml`, and `fnox.orb.toml` own their remaining references and provider overrides. Each environment has one effective set. Host configuration describes the consumer, not a restriction to one 1Password account.

Physical hostname selection is exact after removing an FQDN suffix:

| Short hostname | Profile |
| --- | --- |
| `Thurstons-MacBook-Pro` | `macos` |
| `ML-DFC6YK6VJQ` | `work` |
| `pod042` | `pod042` |

The next planned physical target is `omarchy`. Add its exact hostname and credentials when it is provisioned; do not map unknown Linux machines to it or create an empty active profile in advance.

The Orb entrypoint explicitly selects `orb` and supplies its service identity. An arbitrary unknown hostname or an inherited `FNOX_PROFILE` does not authorize another profile. Unknown hosts fail at secret-consuming or reconciliation entrypoints, not during unrelated lint or dependency tasks.

A small repository launcher, `scripts/fnox-host`, exposes `profile`, `get NAME`, and `exec -- COMMAND ARG...`. Its dedicated Orb invocation selects the runner profile explicitly. It owns identity selection, absolute config location, authentication environment cleanup, and process execution. It does not parse SecretRefs, perform provider lookups itself, persist values, or shadow `op`, `fnox`, or `chezmoi` on PATH. A fnox-launched child carries the nonsecret `ANSIBLONOMICON_EXEC_PROFILE` marker. Nested invocations require a matching profile and the complete declared application set, then reuse those process-local values without reauthentication. This keeps Orb's provider token out of its agent while allowing nested repository tasks. The marker describes trusted process context, not cryptographic provenance; arbitrary inherited API variables without it never select this path.

The launcher loads only the intended root/host declarations through verified native fnox composition. Use an explicit host config with one root import and isolate fnox's global config directory. Isolate global/local configuration and reject synced entries and file-output secret modes. Tests must verify actual effective keys and provider overrides against the installed binary, not just TOML syntax. Profile-file naming changes fnox's merge behavior and must not accidentally select desktop authentication on pod042.

Set `env = "exec"`, strict missing-secret errors, and disable fnox's daemon and authentication retry prompts. Ordinary shells receive no injected values. Native fnox still resolves the whole effective map during `exec`, including `env=false` entries. Consequently the host must be able to resolve its inherited shared set; this broader dependency is accepted. Do not invent operation groups to avoid it.

Shared references should name one logical credential once. Consumer-specific aliases, such as a Cloudflare token's `TF_VAR_*` name, belong at the process boundary. Required credentials have no fallback defaults. Literal account/tunnel identifiers belong in ordinary configuration rather than the secret index.

### Chezmoi

Rendered chezmoi configuration points `[secret].command` at the repository launcher, with `args = ["get"]`. Text templates call `{{ secret "NAME" }}`. Chezmoi owns its per-invocation lookup cache and `--skip-secrets` behavior. A launcher available only after that same apply would be a bootstrap cycle, so the repository/support files must exist before init and rendering.

Plain `chezmoi apply` preserves native semantics: earlier files may already have changed when a later lookup fails. There is no full-scope apply prehook. Full reconciliation runs under strict fnox preflight; direct narrow nonsecret chezmoi operations need not resolve unrelated credentials. Preflight is an availability check, not a transaction: a subsequent lookup or filesystem operation can still fail. Standalone invocations perform native lookups. Invocations inside a validated fnox process context use its already-resolved set; a missing or mismatched set fails rather than falling back to stale values or a different identity.

Ansible uses fatal `chezmoi status` failures and status-based apply decisions, not suppressed diff errors. Automated content previews use `--skip-secrets`; they must not determine whether secret-only updates need applying. Direct operator-requested full diffs may reveal secrets and are not appropriate for automated logs.

### Reconciliation and consumers

Existing public mise task names remain the entrypoints. Secret-consuming tasks run under the inferred host set; dependency/git bootstrap remains secret-free. Full local and remote pod042 runs use the same native target, with capabilities executed serially and Git cleanliness/exact-revision checks unchanged. Root `mise reconcile` must dispatch pod042 to its native driver, never the retired Ansible playbook.

Remote secret resolution occurs on pod042 using its retained identity and persistent guarded checkout. The workstation validates and fast-forwards that checkout, then invokes the local native path over SSH. First access remains a secret-free landing-zone operation and may retain native remote staging. It must not accidentally include future secret-dependent capabilities.

Terraform receives current R2 credentials for init as well as plan/apply, plus the appropriate variable aliases. Automated commands reject missing/empty inputs before invocation and use `-input=false`.

Worker deploy/dev helpers consume environment values, validate every required binding before any Wrangler mutation, and preserve explicit rotation behavior. Upload secrets through stdin, not argv or temporary credential caches. Local development must use a verified Wrangler environment-binding mechanism and reject stale `.dev.vars` that could override it. The existing nine AIG/hooks binding mappings must be accounted for; any retired Worker consumer is removed explicitly, not left with missing credentials.

Agent/MCP launches and work-local consumers must stop depending on ambient `.env`. Use existing supported credential commands or an explicit fnox-backed launch. Provider authentication tokens must never be passed through to application children. Named private application credential files remain permitted; shell-wide exported credentials do not become an alternative cache.

### Service-token installation and alerting

`mise pod042:install-service-token` is attended and separate from first access and reconciliation. It securely installs or rotates the retained 1Password service-account token and proves user/root resolution without printing values. It neither installs tools nor advances the remote checkout. Reconcile first so both checkouts match and fnox/op are available. Ordinary host configuration tracks their latest releases through mise's registry backends, without hand-maintained version or checksum pins. The workstation resolves `POD042_SERVICE_ACCOUNT_TOKEN` by a single named lookup rather than injecting it as an ordinary application credential.

The final pod042 token path remains `/home/thurstonsand/.config/op-service-account/token`, directory mode 0700 and file mode 0600, owned by `thurstonsand`. Root may read it. Transfer uses SSH stdin, never arguments or logs. Reject empty input, symlinks, and unexpected destination types. Validate a replacement before retiring a usable identity; use restrictive atomic replacement and retain no duplicate token. Re-running converges rotation to the declared source.

Pod042's launcher supplies that token to fnox's explicit provider configuration and strips provider tokens and unintended Connect authentication before launching application children. Desktop providers explicitly select the personal or work account and clear inherited service/Connect authority. Orb uses its supplied service identity without writing a retained token or cache.

Hark's credential and failure-delivery command run independently of the checkout, fnox, and 1Password after reconciliation. Deliver the URL through a narrowly scoped private credential file/systemd credential, and avoid URL disclosure in subprocess arguments or logs. Notification failure must not mask the original job failure. Healthchecks registration and heartbeat URLs land with their maintenance timers, not as a dependency of basic Hark delivery.

## Call Stacks and Data Flow

```text
Old shell entry
  mise bootstrap:secrets
    init-secrets.py -> op inject -> .env + Worker .dev.vars
  later mise environment load -> broad inherited secrets

New shell entry / Orb dependency resume
  mise bootstrap -> dependency and Git setup only

Secret-consuming mise task
  fnox-host -> validate host/config and authentication environment
    fnox strict exec -> resolve effective host set
      scrub provider authority -> consumer-specific name mapping
        Ansible / OpenTofu / Wrangler / agent process

Plain chezmoi
  template secret(NAME) -> invocation cache
    fnox-host get NAME -> fnox -> explicit 1Password provider
      text result -> private target file

Remote pod042 reconciliation
  workstation driver -> local/remote Git and hostname guards
    exact guarded fast-forward -> SSH persistent checkout
      local driver -> host fnox preflight -> native mise target
        serial capabilities -> rendered credential files/services

Attended service-token installation/rotation
  validate clean matching pushed revisions and hostname -> named workstation token lookup
    SSH stdin
      validate candidate as root/operator -> restrictive atomic token convergence
        installed-file readback and operator probe -> report changed/no-op and success

Running service failure
  storage-alert -> retained Hark credential -> HTTPS delivery
    preserve producer exit status even if delivery fails
```

Missing provider values stop strict exec before the application starts. Process exit codes and signals propagate. There is no retry through a stale cache and no automatic unattended sign-in. Rerunning reconciliation repairs declared drift; it does not repeat pool imports or other operator-only actions. The token receiver serializes replacement and removes interrupted temporary candidates on rerun.

## Design Decisions

### 1. One effective set per host

Operation profiles would reduce authority and failure coupling, but the user rejected their extra configuration. The starting system effectively exposes global secrets across hosts. Host selection, exec-only injection, and removing dormant credentials are a worthwhile improvement without a second taxonomy of operations.

### 2. Native generic chezmoi integration

Chezmoi already offers the adapter, caching, and skip behavior. Use it rather than an alias, PATH wrapper, duplicated op lookup, or template hook exporting into a parent process. Preserve direct apply semantics rather than requiring all credentials for every narrow apply.

### 3. Explicit account access, including work

Work retains its declared personal-account dependencies, including the current login credential, notify webhook, and font source. The six existing work-token exceptions retain corporate provider routing. Discover full account identifiers during attended verification; do not invent them from known prefixes. Desktop biometric prompt counts require live measurement, not a promise of one prompt.

### 4. One consumer-switch revision

New code can be built and tested while disconnected from public entrypoints. There must be no normal-operation dual writing or incremental split authority. The switch changes all active consumers, removes old loaders, and retires owned cache files together. Offline machines adopt that revision individually; literal simultaneous fleet activation is not possible.

### 5. Persistent service credentials, not a repository cache

The retained pod042 service-account token and named consumer-owned credentials are permitted. Private rendered application files, application credential databases, and Terraform remote state remain intentional persistence. This is not a claim that no application ever stores credentials. Fnox changes resolution, not file permissions, logs, or downstream process behavior; those must be tested separately.

### 6. Remove obsolete paths without deleting live functionality

Audit all 95 old index entries and raw references outside it. Remove dormant declarations and retired executable secret paths, migrate active consumers, and leave vault items untouched. Orb remains supported through fnox. Historical design/evidence references remain historical; current instructions must not direct users to the removed resolver.

## Edge Cases & Failure Modes

- **Shared secret unavailable on one host:** that host's full exec fails. Validate every effective set before activation; do not weaken missing-secret policy to make it pass.
- **Unknown physical host:** refuse secret/reconciliation entrypoints before authentication or mutation; unrelated checks remain usable.
- **Stale ambient credentials:** sanitize inherited credentials at the boundary and require fresh shells/harnesses during activation. A narrow new environment cannot retract secrets already copied into a running tmux server, editor, or agent.
- **Provider outage:** reconciliation fails, existing rendered credentials remain untouched, and Hark continues independently. Direct chezmoi may have applied preceding files as documented.
- **Token rotation failure:** preserve the previously usable installed identity and running service credentials; report failure without values.
- **Unexpected fnox config or sync:** reject rather than allow accidental overrides or cached resolution. `--no-daemon` alone does not prevent sync entries.
- **Secret-bearing diff:** no automated raw diff logging; preserve secret-only drift detection through status.
- **Partial Worker inputs:** no deployment or secret write occurs before complete validation. A later remote API failure is not claimed to be transactional.
- **Work-local source unavailable here:** emit a versioned one-time migration instruction and do not declare work activation complete until local-source review and live checks finish there.
- **Remote staging lacks root declarations:** normal reconciliation resolves from the complete persistent checkout, not a target-only staging directory.
- **Rollback:** roll back consumers/config together. Never silently recreate `.env`; restoring the old cache-based mode would require explicit approval.

## Alternatives

### Operation profiles and named shared consumer groups

- **Status:** Rejected
- **Decision:** The configuration cost exceeds the desired isolation benefit for this repository.
- **Discussion:** Research proved native composition works and that `env=false` cannot substitute for selection. The broader host-set tradeoff is deliberate.

### Hybrid environment-first/1Password template helper

- **Status:** Rejected
- **Decision:** Retains duplicated references and accepts stale ambient values.
- **Discussion:** Keep op for item/document capabilities, not as a parallel ordinary text-secret resolver.

### Chez alias or full-scope apply prehook

- **Status:** Rejected
- **Decision:** Native generic secrets already handle the command interface. Full prehooks impose unrelated availability requirements and duplicate reads without making apply transactional.

## Implementation Plan

Each phase is independently reviewable and must keep existing public entrypoints working. Phases 1 and 2 are disconnected preparation, not two live authorities. Phase 3 is the single consumer switch. No automatic commit, staging, or deployment is implied by this plan.

- [ ] Phase 1: Build and prove the disconnected fnox path
  - Goal: Establish complete consumer accounting and a tested native resolution boundary before activation.
  - Files: `fnox*.toml`, `scripts/fnox-host` and its Python implementation if needed, `tests/`, managed fnox tool declarations, a committed migration inventory under `docs/wayfinding/bunker-rebuild/research/`.
  - Work: Account for all 95 entries, duplicate aliases, external raw text references, worker mappings, agent launches, and work-local dependencies. Classify each as migrated or retired with its consumer. Implement one-set host/Orb selection and token scrubbing. Track latest tool releases through mise registry backends; verify real installation and account identifiers rather than guessing. Leave existing public secret consumers unchanged.
  - Validation: Fake-op tests with the actual installed fnox binary prove selected effective keys/providers, strict failure/no-child behavior, inherited-token cleanup, config isolation, no sync/daemon, and multiline/quoted values. Test unknown hosts and explicit Orb selection. No real values in test output. Focused tests plus `mise run check` pass.

- [ ] Phase 2: Prove attended identity without activating secret consumers
  - Goal: Establish pod042's recoverable headless identity while leaving service behavior unchanged.
  - Files: native identity tool resources, `scripts/pod042_service_token.py`, mise task, identity tests and evidence.
  - Work: Keep tool installation in ordinary reconciliation using mise registry backends tracking latest. The attended service-token command owns only stdin transfer, candidate validation, restrictive atomic convergence and no-value probes. Keep first access secret-free. Use the existing Debian development VM for smoke tests; real pod042 apply requires the existing clean, pushed revision guards and attended authorization.
  - Validation: Fresh install, rerun/no-op, rotation, provider rejection, symlink/type refusal, interrupted transfer, ownership/modes, user/root resolution and application-token exclusion. Real verification reports only versions, identities, permissions and success.

- [ ] Phase 3: Switch every consumer and remove the old system
  - Goal: One stable revision has fnox as its only active text-secret authority.
  - Files: root/bootstrap mise tasks, pod042 driver, chezmoi configuration/templates and Ansible role, Terraform/Worker wrappers, MCP/agent launches, `.agents/resume`, work integration, secret-bearing file attributes, cache retirement declarations, old resolver/tests/dependencies, current documentation.
  - Work: Wire strict exec and native generic secret lookup; fix root pod042 dispatch and remote checkout resolution; retain first-access isolation. Validate/migrate Worker inputs and Terraform aliases, remove ambient shell exports and unsafe automated diffs. Remove dormant references and executable legacy secret adapters after consumer accounting. Delete `.secrets.jsonc` and its resolver, remove dotenv consumers and dependencies only after their final use disappears, retain protective ignore rules, and retire only this repository's owned cache files. Update `CONTEXT.md`, `DEV.md`, `README.work.md`, active instructions and error strings. Add the one-time work-local review notice with a nonsecret receipt.
  - Validation: Unit and actual-binary fixture tests cover every public entrypoint, direct chezmoi outside the repository, cache/skip/partial-apply behavior, secret-only drift, Worker stdin/no-mutation failures, Terraform input checks, agent launch environment, explicit Orb behavior, and first-access/local/remote parity. Sentinel scans prove logs/argv/rendered permissions do not disclose credentials. A repository search contract accounts for every remaining legacy reference. `mise run check` passes.

- [ ] Phase 4: Activate and verify each supported environment
  - Goal: Prove the single switched revision with real authentication and without old caches.
  - Files: migration inventory/evidence, work review instructions and completion receipts, any fixes required by the probes.
  - Work: Use fresh processes. Personal/work verify direct chezmoi and mise calls, actual prompts, account routing and package availability; work inspects the uncommitted files listed in `README.work.md`. Orb proves supplied-token execution without cache generation. Pod042 proves local/remote checks and convergence at the same clean pushed revision. Do not claim an unavailable host is verified.
  - Validation: No-value provider checks; safe chezmoi status/skip-secret previews; read-only Terraform plans/smokes with protected output; Worker dry-run/dev/type checks without `.dev.vars`; pod042 second-run no-op and provider-outage preservation. Live deploys remain separately authorized. Record remaining host-specific blockers rather than inventing parity.

- [ ] Phase 5: Establish independent Hark delivery
  - Goal: Unblock storage maintenance with a working external failure path.
  - Files: native pod042 alerting resources, credential/alert command and tests, capability registration/parity tests, ticket 34 evidence.
  - Work: Render only Hark's service credential and delivery command. Keep it independent of repo/provider availability and preserve producer failure status. Do not require Healthchecks or enable maintenance yet.
  - Validation: Disposable-host convergence/no-op, failed-provider preservation, sentinel argv/log checks and failed-delivery status handling. After authorization, send a named live test and confirm receipt, then prove the installed delivery path does not call fnox/op or read the checkout.
