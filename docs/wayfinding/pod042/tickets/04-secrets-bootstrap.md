---
status: closed
claimed: 2B (charting session)
type: grilling
blocked-by: [12]
---

# Secrets bootstrap for pod042

## Question

How does pod042 get and hold secrets? The OpenClaw pattern — scoped 1Password `agent` vault, service-account token file, `op` wrapper, SecretRef resolver — worked but was inlined into the playbook as ad-hoc tasks. Decide: reuse the same service account and vault, or issue fresh scoped credentials? Extract the pattern into a proper role (it is general enough that future unattended boxes will want it)? What does the unattended-agent threat model require — read-only vault access, token rotation story, what an attacker on the box can reach? Resolve into the secrets design for the new playbook.

### Partial resolution (grilled 2026-07-24)

Three branches settled; the delivery mechanism awaits [Agent-native secrets tooling](12-agent-native-secrets-tooling.md):

- **Service account**: reuse OpenClaw's existing SA (already scoped to the `agent` vault, which holds 66 of 68 `.secrets.jsonc` refs — the two outliers are Mac login passwords pod042 never needs). Rename openclaw→pod042 references as touched.
- **Git credential**: the user's **personal SSH key** lives on the box — deliberate choice over a scoped deploy key ("it's all my infra"). Recorded risk: full GitHub account access rides on an unattended VM.
- **Amp auth**: reuse the existing Amp API key item from the agent vault. pod042 is its only consumer now that cli-proxy-api no longer proxies Amp, and it has no `.secrets.jsonc` ref — the box reads it from the vault directly.

### Final resolution (2026-07-24)

Delivery adopts the [Agent-native secrets tooling](12-agent-native-secrets-tooling.md) recommendation: a minimal reusable **service-account `op` launcher role**; `op inject` populates the converge `.env` cache; systemd services get narrow injection via `op run`/systemd credentials (e.g. `AMP_API_KEY` for the runner — which must NOT receive the broad `.env` or the SA bearer token); chezmoi keeps its existing op templates; OpenClaw's custom protocol-v1 SecretRef resolver retires with OpenClaw (it was the gateway's, not pi's). Connect servers, SDKs, and third-party brokers rejected as unwarranted.

Amendment (user, 2026-07-24): the service account gets **write access to the agent vault**, not just read. The resident agent may provision secrets for itself — sign up for a service, `op item create` the credential into the vault, add the SecretRef to `.secrets.jsonc`, start using it. Self-provisioning is a first-class workflow, not an exception.
