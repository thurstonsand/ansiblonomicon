# Consumer-scoped credentials

Status: Accepted

## Decision

Every consumer requests only the credentials it needs. Agent-vault access uses the shared automation identity without desktop authorization. Private and corporate credentials retain desktop authentication, invoked only when a consumer actually needs them. Bootstrap enrollment and rotation of the shared automation token deliberately remain attended exceptions.

The work code-host tokens are the work-host exception. Corporate 1Password authorizes `op` per terminal with Touch ID, and Pi sessions often run unattended in a fresh tmux pane, so a per-call read fails with nobody there to approve it. The shell task therefore resolves `SOURCEGRAPH_TOKEN`, `GITLAB_ACCESS_TOKEN` and `BITBUCKET_TOKEN` during attended reconciliation and renders them into the work host's zsh environment, where pi-librarian reads them through `tokenEnv`.

This supersedes design 26's whole-host execution rule. The shared identity and provider isolation remain unchanged. Project-wide exports were subsequently retired; entering the repo no longer reads secrets.

## Execution

`fnox-host exec --secret NAME [--secret NAME ...] -- COMMAND` requires at least one selected credential. There is no implicit whole-host execution or `--all` mode. The launcher validates every name against the current host declarations before resolving anything, fetches each selected value through native fnox `get`, and starts the child only after all reads succeed. Get-only `env = false` secrets and the hidden provider token cannot be selected for execution. The child receives only selected canonical credentials, with inherited canonical values and `OP_*`/`FNOX_*` authority removed.

Nested launches carry `ANSIBLONOMICON_EXEC_PROFILE` and `ANSIBLONOMICON_EXEC_KEYS`, a JSON list of selected names. Missing selected values, malformed scope and profile mismatches fail. Only explicitly scoped values can be reused; extra inherited canonical values grant no trust. A declared but unselected `get NAME` resolves just that credential afresh. A narrower child drops the other inherited credentials.

`mise run secrets:check NAME` checks one credential through `get` without printing it. No secret is exported by project activation.

## Consumers

Laptop reconciliation selects its host's sudo password before launching Ansible. Work reconciliation also selects `ANTHROPIC_AUTH_TOKEN` so chezmoi can render the gateway credential into Claude's settings. Its fact cache stays in memory so environment facts cannot persist the scoped credentials, and repeated `SUDO_ASKPASS` calls reuse the selected password without another provider read. Agent launches remain unwrapped. Other task wrappers explicitly select their own keys; connection-time MCP reads and on-demand Parallel reads remain lazy.

Pod042 first-access Agent-vault item operations use a broker that supplies the shared service-account token only to its `op` subprocess. Enrollment of that identity remains attended. This decision does not establish that the live service account has item-write permission.

## Verification

Fake-provider tests cover selection before resolution, an untouched poisoned Private provider, selected personal-provider reads, nested reuse and late reads, token isolation, and failure without child launch or secret output. Work activation remains deferred to its attended local review; no Work audit or Home Assistant probe is implied by these tests.
