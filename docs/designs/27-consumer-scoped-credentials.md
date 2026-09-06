# Consumer-scoped credentials

Status: Accepted

## Decision

Every consumer requests only the credentials it needs. Agent-vault access uses the shared automation identity without desktop authorization. Private and corporate credentials retain desktop authentication, invoked only when a consumer actually needs them. Bootstrap enrollment and rotation of the shared automation token deliberately remain attended exceptions.

This supersedes design 26's whole-host execution rule. Its shared identity, provider isolation, six project exports and native mise cache remain unchanged.

## Execution

`fnox-host exec --secret NAME [--secret NAME ...] -- COMMAND` requires at least one selected credential. There is no implicit whole-host execution or `--all` mode. The launcher validates every name against the current host declarations before resolving anything, fetches each selected value through native fnox `get`, and starts the child only after all reads succeed. Get-only `env = false` secrets and the hidden provider token cannot be selected for execution. The child receives only selected canonical credentials, with inherited canonical values and `OP_*`/`FNOX_*` authority removed.

Nested launches carry `ANSIBLONOMICON_EXEC_PROFILE` and `ANSIBLONOMICON_EXEC_KEYS`, a JSON list of selected names. Missing selected values, malformed scope and profile mismatches fail. Only explicitly scoped values can be reused; extra canonical values, including exports added by mise, grant no trust. A declared but unselected `get NAME` resolves just that credential afresh. A narrower child drops the other inherited credentials.

`fnox-host export` still uses the six `env = true` project credentials. Inside a partial scope it reuses selected values and resolves missing export keys individually. Mise retains its native encrypted environment cache; this decision adds no secret cache. `mise run secrets:check NAME` checks one credential through `get` without printing it.

## Consumers

Normal Ansible and agent launches do not use an exec wrapper. `SUDO_ASKPASS` resolves the Private-vault password only when sudo requests it. Task wrappers explicitly select their own keys; connection-time MCP reads and on-demand Parallel reads remain lazy.

Pod042 first-access Agent-vault item operations use a broker that supplies the shared service-account token only to its `op` subprocess. Enrollment of that identity remains attended. This decision does not establish that the live service account has item-write permission.

## Verification

Fake-provider tests cover selection before resolution, an untouched poisoned Private provider, selected personal-provider reads, nested reuse and late reads, token isolation, and failure without child launch or secret output. Work activation remains deferred to its attended local review; no Work audit or Home Assistant probe is implied by these tests.
