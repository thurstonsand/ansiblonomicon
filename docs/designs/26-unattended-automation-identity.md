# Unattended automation identity

Status: Accepted

## Decision

Use the existing shared 1Password automation service account across personal machines, pod042 and ephemeral runners. Work enrollment remains attended future work; Omarchy can use the same mechanism when its host configuration exists. Rotation deliberately requires updating every enrolled environment rather than managing separate service accounts.

The agent vault is the unattended boundary. Private-vault reads retain desktop authentication. Ordinary `op` remains the real CLI; do not export `OP_SERVICE_ACCOUNT_TOKEN` or its fnox equivalent into the shell and thereby change its account selection.

This updates design 25's agent-launch and shell-environment rules. The per-host secret declarations, explicit whole-host execution, provider-token isolation, independent service credentials and cache retirement remain in effect.

## Identity

Persistent desktop hosts store the shared token as a hidden `env = false` secret in native `~/.config/fnox/config.toml`, with owner-only permissions. The agent provider references that secret. Fnox supplies its value only to the provider's `op` process; the shell and applications do not receive the provider token.

Enrollment uses attended desktop access to the existing declared token reference, tests the candidate through fnox, and atomically installs it. Failed authentication or candidate verification must preserve the previous identity. The token file is an authentication credential, not a cache of resolved application secrets.

Pod042's established operator-owned token and root/operator access remain supported. Orb continues to receive its identity privately from the runner. Neither requires a desktop session. Work's corporate providers remain separate from personal agent-vault access; the shared personal service account cannot grant corporate or built-in Private-vault access.

## Consumption

No secret currently needs a global shell export. Ordinary settings such as PATH remain global and identical for the human and launched programs.

Inside ansiblonomicon, repo-local mise configuration loads `scripts/project-secrets.sh` through native `env._.source` after `mise trust`. The script calls `fnox-host export`, which forwards native `fnox export --format shell` and exports only explicitly marked `env = true` credentials for Cloudflare, gateway administration, Access and R2. Mise removes those exports when the shell leaves the project. Credentials for MCPs are resolved at connection time instead of requiring that the agent start in this directory.

`CLI_PROXY_API_KEY` remains the AIG Worker's inbound authentication secret, not a local shell variable. `PARALLEL_API_KEY` belongs to its consumers: Pi resolves it when a Parallel operation needs a client, OpenCode retains its rendered MCP authorization header, and Zed no longer configures Parallel.

Agent launch functions no longer run `fnox-host exec`. A fresh Pi launch from any directory must not prefetch the whole host set. The Pi web-tools package accepts a trusted global `webTools.parallel.apiKeyCommand`; registration does not execute that command. Each actual operation obtains a fresh key without changing `process.env` or writing a secret cache.

Explicit `fnox-host exec` remains a whole-host operation for reconciliation and existing task entrypoints. It can request Private-vault authorization. It is not an implicit prerequisite to starting an editor or agent.

## Native behavior that matters

Fnox 1.35.x `exec` resolves the complete active set before suppressing `env = false` values. In contrast, `export` and `hook-env` filter to shell-enabled secrets before resolution, and `get` resolves one requested key. A hidden token can still resolve as the internal dependency of an exported agent-vault secret without itself being exported.

Native fnox configuration layers the global identity beneath project configuration, including projects with `root = true`. The global identity therefore contains only its hidden token, not project secret declarations. Mise owns project credentials, PATH, tools and virtualenv activation. Its native encrypted environment cache is enabled, including resolved application secrets, and the source directive marks those values for log redaction. The encryption key belongs to the shell session and reaches its children as `__MISE_ENV_CACHE_KEY`, so it is not a security boundary against those children. The native cache TTL defaults to one hour; fnox declarations and the identity file are not additional mise watch dependencies. Changes to those inputs can therefore leave cached project exports stale until expiration. Direct `fnox-host get` and Pi's per-request credential command do not use that environment cache. There is no custom cache, sync file, daemon or experimental mise environment plugin.

Initial enrollment uses `mise --no-env exec -- python3 scripts/automation_identity.py`, so obtaining the identity does not first require a working credential export. Provider failures during normal activation stop the source script before it evaluates any partial output.

Do not enable fnox's global automatic shell hook. It lacks a trust gate, so an arbitrary repository's fnox configuration could request access merely when entering its directory. Mise supplies the trust boundary for personal projects. Direnv remains installed and its shell hook remains available for external repositories; ansiblonomicon has no `.envrc`.

The chosen convenience tradeoff is deliberate: processes launched inside the project inherit its exported credentials. Processes elsewhere do not receive them merely because their owner also uses ansiblonomicon.

## Verification

Use fake `op` commands to prove native export filtering, private-provider separation, failed enrollment preservation and omission of provider authority from children. On an enrolled Mac, prove agent-vault reads with desktop integration disabled, project entry/exit export behavior, a fresh Pi startup without inherited credentials, and an actual on-demand Parallel search. Preserve OpenCode's configuration and verify Zed's Parallel server is absent. Do not claim Work or Omarchy activation from these Mac checks.
