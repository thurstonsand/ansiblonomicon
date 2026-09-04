# Agent-native 1Password secrets for pod042

Researched 2026-07-24. This assesses a headless Debian 13 VM with the already-decided, read-scoped `agent`-vault service account. It does not revisit the service-account, personal-SSH-key, or Amp-API-key decisions in [Secrets bootstrap for pod042](../tickets/04-secrets-bootstrap.md).

## Decision

**Keep the 1Password service account and adopt the first-party `op` CLI as the one runtime mechanism. Extract the useful part of OpenClaw's file-to-environment adapter into a small reusable Ansible role, but retire the custom JSON SecretRef resolver.**

The role should install the official `1password-cli`, accept the first-provision `OP_SERVICE_ACCOUNT_TOKEN`, write it to a `0700` per-user secret directory as a `0600` file, and install a tiny `op` launcher. The launcher reads `OP_SERVICE_ACCOUNT_TOKEN_FILE` (defaulting to that managed file), exports `OP_SERVICE_ACCOUNT_TOKEN` only while it `exec`s the real `op`, and otherwise adds no protocol, cache, daemon, or dependency. This is simply the ergonomic adapter that 1Password's CLI environment-variable convention lacks; it is not a new secret broker.

Use first-party `op inject` for the existing `.secrets.jsonc` → `.env` materialization, and `op run` for a long-lived service's *specific* runtime secrets. Do not put the service-account token in a global shell profile or a systemd `Environment=` directive.

## Why this is the fit

1Password explicitly positions service accounts as automated, least-privilege CLI authentication without an additional service. The supported service-account commands include `op read`, `op inject`, and `op run`; its own current guidance calls the CLI plus a service account the lightweight option for shared automation, CI, task runners, and infrastructure work. This is exactly pod042's shape.

The token remains a bearer credential for the complete `agent` vault. `0600` storage and systemd credentials reduce accidental exposure, but do not turn a root/user compromise or a malicious process running as the pod042 user into a safe event. The already-set vault scope remains the real boundary. Rotate/revoke the token in 1Password, replace the managed file, then restart/reconverge affected units; 1Password supports both rotation and revocation.

## Consumer contract

| Consumer | Delivery | Why |
| --- | --- | --- |
| Converge (`uv run poe pod042`) | Run the existing `init-secrets.py` through the role's `op` launcher. Keep its one-call `op inject` template expansion and its `0600` generated `.env`. Rename its OpenClaw hostname special case to pod042 or make it role-driven. | The current Ansible/direnv workflow requires a persistent `.env`; `op run` deliberately supplies values only to its child and cannot replace that cache without changing the broader workflow. |
| Amp systemd runner | Give the unit the service-account *file* with `LoadCredential=`, set `OP_SERVICE_ACCOUNT_TOKEN_FILE=%d/op-service-account-token`, and start Amp through `op run --env-file=<small committed refs file> -- …`. That refs file should contain only `AMP_API_KEY=op://…`, never the generated repository `.env`. The command shim must `unset OP_SERVICE_ACCOUNT_TOKEN OP_SERVICE_ACCOUNT_TOKEN_FILE` before it `exec`s Amp. | systemd passes the token as a unit-private credential file, while `op run` injects only Amp's API key for the runner lifetime. It avoids handing the resident agent every cached infrastructure secret or the 1Password bearer token. |
| Chezmoi templates | Keep `op-secret`: it uses an already-resolved environment value when `init-secrets` has populated one, then falls back to `onepasswordRead`. At Ansible-driven `chezmoi apply`, read the managed token with `no_log` and pass `OP_SERVICE_ACCOUNT_TOKEN` only to that command, replacing the role's OpenClaw-only path/hostname special case. | `onepasswordRead` is the correct first-party Chezmoï integration. It needs the service-account environment convention, not a separate resolver. |
| Ad-hoc admin/agent shell | The launcher makes `op read op://…`, `op inject`, and `op run` work without manually exporting a token. Prefer `op run --env-file=<narrow refs file> -- command` when a command needs a secret; use `op read` only where the value must become a file or a human-visible value. | This preserves the practical advantage of the incumbent without placing the token in every shell's inherited environment. |

### The systemd detail matters

`LoadCredential=`/`ImportCredential=` are a delivery mechanism, not a 1Password backend: they still need the service-account token to exist somewhere at bootstrap. They are worthwhile for the Amp unit because systemd mounts the loaded credential at `$CREDENTIALS_DIRECTORY`, scopes it to the service user, and does not propagate it down the process tree. They also support encrypted credential stores, but host-key/TPM encryption is only defense in depth on a machine which must itself decrypt the service-account token.

The launcher needs to honor `OP_SERVICE_ACCOUNT_TOKEN_FILE`, so the same code works in a login shell and a unit. `op run` may be used only for the command that needs the final secret. Its child environment must be tested to ensure the service-account variables are unset before Amp starts; explicit unsetting is cheap, and the runner must never receive a token that can read the vault. The runner will necessarily receive `AMP_API_KEY`, and Amp-subprocess inheritance still makes that key reachable by the runner's executed tools. That is the narrow authority deliberately chosen for this service.

## Landscape comparison

| Option | Assessment for pod042 |
| --- | --- |
| **`op` service account + `op inject` / `op run`** | **Adopt.** Official, installed already, works non-interactively, and covers every consumer. `op inject` is appropriate where the repository contract needs a `0600` file; `op run` injects variables only for a subprocess and masks secret-looking output by default. Use ID-form secret references where practical to reduce service-account request usage. |
| Direct `OP_SERVICE_ACCOUNT_TOKEN` in a shell/unit environment | Do not use. It is the documented authentication input, but exporting it globally unnecessarily hands a vault bearer token to every child process. Store it in a private file and bridge it only into an `op` invocation. |
| 1Password CLI shell plugins | Not applicable. They authenticate third-party CLIs through fingerprint, Apple Watch, or system authentication. That is good interactive-workstation ergonomics, not unattended service-account automation. |
| 1Password SDK | Do not add. The Go/JS/Python SDKs still take the same service-account token, are version-0 packages, and help only a purpose-built application. They do not improve Ansible, chezmoi, direnv, or arbitrary shell commands. Reconsider only if pod042 gains a native secrets-aware daemon needing typed API access or connection pooling. |
| 1Password Connect | Do not add. Connect brings two containers, a Connect credential file, per-client access tokens, and a local REST/cache layer. Its advantages are REST integration, low latency, and no service-account request quotas. Pod042 has low-volume CLI/template traffic and no application needing a REST API; adding it duplicates the static-secret bootstrap problem. |
| systemd credentials alone | Use as a *unit transport* only. They improve at-rest and per-service handling but neither retrieve from 1Password nor eliminate the initial bearer token. |
| direnv | Retain for an interactive repository shell and the existing `.env` cache. Do not make it the service identity: a systemd user service should declare its own narrow `op run` path and must not inherit a developer shell's complete `.env`. |
| 1Password Environments, local `.env` mounts, agent hook, MCP server | Do not adopt for pod042. These are useful beta desktop-agent features, but the local mount and MCP flow require a running 1Password desktop app and explicit authorization prompts. They are not an unattended Linux VM mechanism. They may later improve a human workstation's agent workflow without replacing this VM design. |
| 1Password Credential Broker | Watch, do not adopt. It is a promising first-party workload-identity design, but private beta currently supports GitHub Actions; machine and AI-agent integrations are explicitly future work. A TrueNAS VM cannot use it today. |
| Third-party agent secret brokers/MCP wrappers | Do not add. They introduce another resident daemon or SaaS credential, normally still need the 1Password token, and duplicate the CLI mechanism. The first-party Environment MCP server intentionally never returns secrets to the model, but is desktop-authorized rather than headless. |

## Amp is not the secret injector

Amp supports an `AMP_API_KEY` for unattended CLI use, but its documented security feature is **best-effort redaction**, not secret delivery or access control. It detects many common token formats before thread/tool/cloud transmission, but says non-standard, encoded, and obfuscated secrets can evade detection. Treat this as leak mitigation, not a reason to give Amp a vault token or a broad `.env`. The systemd `op run` envelope above is the injection boundary.

## The incumbent resolver is not an agent-harness protocol

The `protocolVersion: 1` JSON resolver in `ansible/playbooks/openclaw.yml` and `chezmoi/dot_local/libexec/executable_openclaw-op-secret` implements **OpenClaw's `secrets.providers.*.source: "exec"` SecretRef provider protocol**. The local Chezmoï template `openclaw-client-config.json.tmpl` configures it for the OpenClaw gateway token. It is not consumed by Pi or the repository's `agent_harness` role; repository and installed-Pi searches found no such configuration. OpenClaw runs it to resolve configured SecretRefs before starting a gateway/client process.

Pod042 is replacing OpenClaw, so copying that protocol would retain an OpenClaw-specific adapter with no consumer. Delete/retire the server-side resolver during OpenClaw sunset. Keep the unrelated Chezmoï resolver only until the OpenClaw client configuration is removed from workstations; do not rename it as pod042 infrastructure.

## Migration checklist for ticket 04 / implementation

1. Create a reusable role, e.g. `onepassword_service_account`, owning the CLI package prerequisite, `0700` token directory, `0600` token file, bootstrap assertion/copy, and the minimal launcher. Its variables supply the owner, token path, and bootstrap environment variable; no hostname literals.
2. Provision pod042 with the already-decided existing `agent`-vault token. Verify as the managed user with `op user get --me`, then `op read` of one permitted item; ensure an out-of-scope item fails.
3. Change `scripts/init-secrets.py` from OpenClaw-specific wrapper detection to the generic pod042/role contract. Preserve its single `op inject` call and `0600` cache. Run `uv run poe init-secrets` non-interactively after a clean cache removal, then prove the expected `.env` exists and is mode `0600`.
4. Convert the Chezmoï role's OpenClaw-only slurp/environment tasks to role variables and verify both its cached-value and `onepasswordRead` fallback paths.
5. Give the Amp unit a `LoadCredential=` token plus a narrow `AMP_API_KEY` reference manifest. Verify `amp --no-tui` starts and `systemctl show`/`/proc` do not expose the service-account token; verify its child environment lacks `OP_SERVICE_ACCOUNT_TOKEN` while Amp retains `AMP_API_KEY`.
6. Remove the inlined OpenClaw bootstrap block and the OpenClaw SecretRef resolver when the legacy client/gateway configuration is removed. Never use `EnvironmentFile=` pointing at the repository-wide generated `.env` for the Amp runner.
7. Record a token-rotation runbook: rotate/revoke in 1Password, update the seed file through a protected convergence, restart dependent units, run `op user get --me` and the converge smoke test, and inspect 1Password's service-account usage report.

## Sources

All external sources checked 2026-07-24.

- [1Password service accounts](https://developer.1password.com/docs/service-accounts/) and [service-account CLI use](https://developer.1password.com/docs/service-accounts/use-with-1password-cli/) — non-interactive token convention, supported commands, scopes, request limits.
- [`op run`](https://developer.1password.com/docs/cli/reference/commands/run/) and [`op inject`](https://developer.1password.com/docs/cli/reference/commands/inject/) — ephemeral environment injection/masking and generated-file semantics.
- [Service-account security](https://developer.1password.com/docs/service-accounts/security/) — rotation and revocation.
- [1Password Secrets Automation comparison](https://developer.1password.com/docs/secrets-automation/) and [Connect](https://developer.1password.com/docs/connect/) — service-account versus Connect tradeoffs and Connect deployment/token requirements.
- [1Password SDKs](https://developer.1password.com/docs/sdks/) and [shell plugins](https://developer.1password.com/docs/cli/shell-plugins/) — SDK scope/version status and interactive-auth design.
- [1Password Environments](https://www.1password.dev/environments), [local `.env` mounts](https://www.1password.dev/environments/local-env-file), [agent hook](https://www.1password.dev/environments/agent-hook-validate), and [MCP server](https://www.1password.dev/environments/mcp-server) — beta/desktop authorization constraints.
- [1Password Credential Broker](https://1password.com/product/credential-broker) — private-beta GitHub Actions coverage and future agent/machine integrations.
- [systemd credentials](https://systemd.io/CREDENTIALS/) — credential lifetime, per-unit access, stores, encryption, and `LoadCredential=`/`ImportCredential=` behavior.
- [Amp Security Reference](https://ampcode.com/security) — `AMP_API_KEY` client storage and best-effort secret redaction.
- [OpenClaw secrets](https://docs.openclaw.ai/gateway/secrets) — the protocol-v1 exec SecretRef provider consumed by the legacy resolver.
