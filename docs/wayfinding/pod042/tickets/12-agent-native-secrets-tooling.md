---
status: closed
claimed: subagent-secrets-research
type: research
blocked-by: []
---

# Agent-native secrets tooling

## Question

Surfaced while grilling [Secrets bootstrap for pod042](04-secrets-bootstrap.md): rather than re-extracting OpenClaw's hand-rolled pattern (SA token file + `op` wrapper script + custom SecretRef resolver), is there a more agent-native, ergonomic way to give unattended machines and their resident agents access to a 1Password service account? Survey the current (2026) landscape: first-party op CLI patterns (`op run`, `op inject`, `OP_SERVICE_ACCOUNT_TOKEN` env conventions), 1Password Connect / SDKs, systemd `LoadCredential`/`ImportCredential` integration, direnv integration, and any purpose-built secret brokers for AI agents — including whether Amp itself has secret-injection or credential-redaction facilities. Judge against pod042's actual consumers: the converge wrapper (`poe pod042` needs `.env` via init-secrets), systemd services (Amp runner needs `AMP_API_KEY`), chezmoi templates, and ad-hoc agent shell use. Deliver a recommendation: adopt a tool/pattern, or bless-and-extract the existing wrapper into a role.

## Resolution

Adopt first-party `op` CLI service-account delivery: extract OpenClaw's private token-file and minimal `op` launcher into a reusable role; retain `op inject` for the required generated `.env`, use `op run` plus systemd `LoadCredential=` for a narrowly injected Amp API key, and keep Chezmoï's native `onepasswordRead` fallback. Do not add Connect, SDKs, desktop-authorized Environments/MCP tooling, third-party brokers, or the Credential Broker beta. The protocol-v1 resolver is OpenClaw's exec SecretRef protocol, not Pi/agent_harness, so retire it with OpenClaw rather than porting it. Details and migration checks: [agent-native secrets research](../assets/agent-native-secrets.md).
