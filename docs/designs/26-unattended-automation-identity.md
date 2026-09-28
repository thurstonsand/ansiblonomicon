# Unattended automation identity

Status: Accepted; execution scope superseded by [27: Consumer-scoped credentials](27-consumer-scoped-credentials.md).

## Decision

Use the existing shared 1Password automation service account across personal machines, pod042 and ephemeral runners. Work enrollment remains attended future work; Omarchy uses the same identity. Rotation deliberately requires updating every enrolled environment rather than managing separate service accounts.

The agent vault is the unattended boundary. Private-vault reads retain desktop authentication. Ordinary `op` remains the real CLI; do not export `OP_SERVICE_ACCOUNT_TOKEN` or its fnox equivalent into the shell and thereby change its account selection.

This updates design 25's agent-launch and shell-environment rules. The per-host secret declarations, explicit whole-host execution, provider-token isolation, independent service credentials and cache retirement remain in effect.

## Identity

Persistent desktop hosts store the shared token as a hidden `env = false` secret in native `~/.config/fnox/config.toml`, with owner-only permissions. The agent provider references that secret. Fnox supplies its value only to the provider's `op` process; the shell and applications do not receive the provider token.

Enrollment uses attended desktop access to the existing declared token reference, tests the candidate through fnox, and atomically installs it. Failed authentication or candidate verification must preserve the previous identity. The token file is an authentication credential, not a cache of resolved application secrets.

Pod042's established operator-owned token and root/operator access remain supported. Orb continues to receive its identity privately from the runner. Neither requires a desktop session. Work's corporate providers remain separate from personal agent-vault access; the shared personal service account cannot grant corporate or built-in Private-vault access.

## Consumption

No secret currently needs a global shell export. Ordinary settings such as PATH remain global and identical for the human and launched programs.

Inside ansiblonomicon, mise activates tools and the virtualenv without reading credentials. Consumers request only their named secrets through `fnox-host get` or `fnox-host exec`; MCP credentials resolve at connection time rather than requiring an agent to start in this directory.

`CLI_PROXY_API_KEY` remains the AIG Worker's inbound authentication secret, not a local shell variable. `PARALLEL_API_KEY` belongs to its consumers: Pi resolves it when a Parallel operation needs a client, OpenCode retains its rendered MCP authorization header, and Zed no longer configures Parallel.

Agent launch functions no longer run `fnox-host exec`. A fresh Pi launch from any directory must not prefetch the whole host set. The Pi web-tools package accepts a trusted global `webTools.parallel.apiKeyCommand`; registration does not execute that command. Each actual operation obtains a fresh key without changing `process.env` or writing a secret cache.

Explicit `fnox-host exec` remains a whole-host operation for reconciliation and existing task entrypoints. It can request Private-vault authorization. It is not an implicit prerequisite to starting an editor or agent.

## Native behavior that matters

Fnox 1.35.x `exec` resolves the complete active set before suppressing `env = false` values. The launcher uses `get` to resolve one requested key at a time; the hidden token resolves only as an internal dependency of an agent-vault secret and is never exported.

Native fnox configuration layers the global identity beneath project configuration, including projects with `root = true`. The global identity therefore contains only its hidden token, not project secret declarations. Mise owns PATH, tools and virtualenv activation. Application credentials are resolved per consumer, without a project-wide export or credential cache.

`fnox-host` builds the resolver's PATH without mise shims: a shim would resolve the calling directory's environment before executing `op`, causing re-entry into mise.

Initial enrollment uses `mise --no-env exec -- python3 scripts/automation_identity.py` to avoid project environment resolution while installing the identity.

Do not enable fnox's global automatic shell hook. It lacks a trust gate, so an arbitrary repository's fnox configuration could request access merely when entering its directory. Mise supplies the trust boundary for personal projects. Direnv remains installed and its shell hook remains available for external repositories; ansiblonomicon has no `.envrc`.

Processes launched inside the project inherit no credentials merely by entering it.

## Verification

Use fake `op` commands to prove private-provider separation, failed enrollment preservation and omission of provider authority from children. On an enrolled Mac or Omarchy laptop, prove agent-vault reads with desktop integration disabled, a fresh Pi startup without inherited credentials, and an actual on-demand Parallel search. Preserve OpenCode's configuration and verify Zed's Parallel server is absent.
