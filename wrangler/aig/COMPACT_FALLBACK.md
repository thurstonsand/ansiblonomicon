# Compact Endpoint Fallback

If AI Gateway has issues with the `/v1/responses/compact` proxy flow (e.g., response size limits, timeouts), you can bypass it by routing directly to cli-proxy-api.

## Current Flow (via AI Gateway)

```
aig.thurstons.house/v1/responses/compact
  → AI Gateway
  → cli-proxy-api/v0/management/api-call
  → api.openai.com/v1/responses/compact
```

## Fallback Flow (direct to cli-proxy-api)

```
aig.thurstons.house/v1/responses/compact
  → cli-proxy-api/v0/management/api-call
  → api.openai.com/v1/responses/compact
```

## How to Switch

In `worker.js`, find the `proxyViaManagementAPI` function and change:

```javascript
// Current (via AI Gateway):
const targetUrl = `${GATEWAY_BASE}/${env.ACCOUNT_ID}/${env.GATEWAY_ID}/custom-cli-proxy-api/v0/management/api-call`;
headers.set("cf-aig-authorization", `Bearer ${env.AIG_TOKEN}`);
```

To:

```javascript
// Fallback (direct to cli-proxy-api):
const targetUrl = `${ORIGIN}/v0/management/api-call`;
// Remove AI Gateway auth header (not needed for direct routing)
```

Then redeploy with `uv run poe wrangler:aig`.
