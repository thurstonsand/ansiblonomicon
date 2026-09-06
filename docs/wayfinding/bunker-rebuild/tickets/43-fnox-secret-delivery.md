---
status: open
type: implementation
blocked-by: [33]
---

# Implement fnox secret delivery

## Objective

Implement [design 25](../../../designs/25-fnox-secret-delivery.md): replace the repository secret cache with fnox and 1Password, keep one effective secret set per physical host or Orb environment, preserve native chezmoi commands, and establish independent pod042 Hark delivery before storage maintenance.

## Execution boundary

The user approved design 25 and implementation, naming this machine's target `macos` and identifying `omarchy` as the next planned target. Follow the design's five phases; disconnected preparation may be reviewed separately, but all active consumers switch together in one revision. Preserve staged/unstaged review state and concurrent edits. Commit, push and live deployment remain explicit operator decisions.

Fresh pod042 never runs its retired Ansible playbook. Keep local/remote native declarations equivalent, serial execution, exact clean pushed-revision guards, and secret-free first access. Use a separate attended service-token installation/rotation command. Transfer provider tokens through stdin and keep them out of application children.

## Completion evidence

- [ ] Account for all 95 old index entries and every additional active text-secret reference. Migrate active consumers, remove dormant declarations and legacy executable paths, and leave vault items untouched.
- [x] Prove native root/host composition with the installed fnox binary and fake op. One effective set per host, no operation groups, no stale/global/local/sync fallback, strict missing-secret errors and explicit account routing.
- [ ] Prove direct chezmoi generic secrets, invocation caching, skip-secrets, and documented partial-apply failure behavior. Automated reconciliation preflights credentials and never logs secret-bearing diffs.
- [x] Prove pod042 attended token installation, rotation and failure preservation, then activate it on the physical NAS.
- [ ] Switch mise, chezmoi, Terraform, Workers, agent/MCP launches and Orb together. Remove `.env`/`.dev.vars` loaders, cache generation and ambient secret exports; retire owned materializations without touching unrelated projects.
- [ ] Fix root pod042 dispatch and resolve remote secrets from its guarded persistent checkout. First access remains independent of fnox identity.
- [ ] Pass focused tests and `mise run check`, including sentinel leakage tests and effective key/provider assertions.
- [ ] Verify macos, work, Orb and pod042 separately. Work gets the one-time local-source review notice; do not claim its uncommitted consumers work until checked there.
- [ ] Prove Hark delivery survives checkout/provider unavailability and delivery errors preserve the producer's failure. Confirm an authorized live notification.

## Implementation progress

Phase 1's disconnected launcher and declarations are implemented in `scripts/fnox-host`, `scripts/fnox_host.py` and the five root fnox TOML files, with fnox tracking `latest` as a repository tool. Initial validation used fnox 1.35.1; mise verified the release checksum and GitHub artifact attestation. Public consumers still use the existing resolver; no host or service has switched.

The launcher tests use fake credentials with the real installed fnox binary. They cover exact `macos`/work/pod042 selection, unknown-host rejection, explicit Orb selection, private token files, actual checked-in root/host composition, provider-token removal, stale environment cleanup, strict failure before child execution, single-key reads, isolated global/local overrides and child exit status. Fable found a validator/config mismatch and a subprocess cancellation bug; the corrected launcher accepts only the declared service-token slot and becomes fnox with `exec`. Permanent SIGINT/SIGTERM tests prove delayed graceful cleanup and exit status preservation. After the final retained-service declarations, all 35 launcher tests, the full 297-test Python suite and `mise run check` passed. Fable verified the corrections. The fake op now handles account flags before the verb; permanent tests assert actual native batches and provider routing rather than silently falling back to individual reads. These results do not establish live provider or deployment readiness.

The [consumer inventory](../research/fnox-consumer-inventory.md) accounts for all 95 old entries: 67 retained, 21 retired, five canonical aliases and two ordinary identifiers. The declarations contain 69 unique remote references; the injected host sets contain 33 macos, 38 work, 59 pod042 and 31 Orb keys. Work account metadata/local-source review and the other hosts' live identity proofs remain pending.

The user confirmed Orb retains repository workflow parity, including Cloudflare, UniFi and Workers. Surviving NAS service references migrate under pod042 without activating services. Ticket 38 must remove associated credential declarations when retiring a service; TrueNAS administration/SSH and Storj-node-only references retire now with their already-retired consumers.

### Attended service-token installation

`mise pod042:install-service-token [--host pod042]` now has a controller and stdin-only receiver in `scripts/pod042_service_token.py`. The controller requires clean matching pushed checkouts and the correct remote hostname/branch. It resolves `POD042_SERVICE_ACCOUNT_TOKEN` on the workstation and sends it through SSH stdin. It does not advance the remote checkout or install tools; ordinary reconciliation must run first. Root and operator must both resolve the candidate before the receiver atomically replaces the retained mode-0600 file. Symlinks, foreign ownership, nonregular files and hard-linked token files are rejected; provider diagnostics are not forwarded into logs.

A disposable Debian container with synthetic credentials and a fake fnox command proved first installation, an unchanged rerun, rotation, rejected-candidate preservation, root/operator probes, permissions, ownership, temporary-file cleanup and diagnostic suppression. After Fable review, the receiver also checks the installed file through the launcher contract, serializes replacement and sweeps interrupted candidates, repairs group/directory drift, and prevents root-owned Python cache files in the checkout. Value-free receiver status/errors reach the operator; raw provider output stays suppressed.

The user rejected the hand-pinned HTTP downloads and custom checksum installer during review. Tool acquisition belongs in ordinary base reconciliation, using mise registry backends tracking latest. The existing OrbStack Debian VM exposed a native Aqua discovery bug for `1password/cli`: registry membership does not mean `latest` resolves. Base now declares `fnox = "latest"` and `op = "latest"` in `/etc/mise/host-tools.toml`, using the default registry backends. Each base reconciliation installs missing tools, runs `mise upgrade` serially, and publishes stable `/usr/local/bin` links. There is no separate update timer. Mise's default 24-hour release age selected fnox 1.35.0 during verification; op resolved to 2.39.0.

The existing OrbStack Debian VM proved clean installation, unchanged rerun, missing/wrong-link repair, missing-source rejection and root/operator binary discovery using the actual base task commands. Test-created resources were cleaned up; physical pod042 was not contacted. Native bootstrap plan checks the declared configuration file, not task-managed binaries or links; dry-run prints the task commands but does not prove their convergence. Apply checks executable sources before publishing links.

Fnox's backend verifies release checksums and GitHub attestations. The default op vfox plugin downloads from 1Password over HTTPS but supplies no checksum/signature verification, despite mise logging a checksum-verification message. Its bundled `op.sig` is not verified. No custom verifier was added.

The user prefers provisioning smoke tests over mock-heavy unit coverage. Removed the mocked prerequisite/orchestration tests; retained actual fnox behavior checks, real filesystem safety checks and existing mise silent-failure regression tests. `mise pod042:install-service-token` on the dirty workstation refused before remote contact with `workstation checkout has local changes`. That guard check did not read or install a real token.

### Physical deployment, 2026-09-06

The user authorized commit and deployment to physical pod042, preferring direct NAS work over further VM cycles. Initial apply found that `/etc/mise` was missing; the VM had already supplied that parent directory. Added its native directory declaration and amended the deployment commit. Base reconciliation then installed fnox 1.35.0 and op 2.39.0 successfully; a second apply reported converged files/services and current tools.

Attended service-token installation passed root/operator candidate and installed-file probes. A second invocation reported unchanged. The retained directory/file are operator-owned modes 0700/0600. Full host exec resolved all 59 declared credentials as both operator and root, with no `OP_` or `FNOX_` authority in either application child. No secret values were logged. Both `ark` and `black-box` remained ONLINE. Existing public consumers still use the legacy resolver; atomic consumer migration and independent Hark delivery remain ahead.

## Follow-up

Ticket 34 owns storage policy and its separate implementation ticket. Healthchecks registration lands with the timers it supervises. This ticket does not enable scrubs, SMART schedules, sanoid or ZFS feature upgrades.
