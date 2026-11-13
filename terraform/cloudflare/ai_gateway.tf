# Requests need cf-aig-authorization with the token in 1Password "Cloudflare/ai gateway/api token".
resource "cloudflare_ai_gateway" "llms" {
  account_id                 = local.account_id
  id                         = "llms"
  authentication             = true
  collect_logs               = true
  cache_ttl                  = 0
  cache_invalidate_on_update = false
  rate_limiting_interval     = 0
  rate_limiting_limit        = 0
  rate_limiting_technique    = "fixed"
  retry_max_attempts         = 3
  retry_delay                = 1000
  retry_backoff              = "exponential"
}

import {
  to = cloudflare_ai_gateway.llms
  id = "${local.account_id}/llms"
}

# =============================================================================
# CUSTOM PROVIDER (via API; the provider has no resource for it)
# =============================================================================
#
# Provider Name: CLI Proxy API
# Provider Slug: cli-proxy-api
# Provider ID: 3f48ce83-8eed-4a83-b755-f1acca99ac21
# Base URL: https://cli-proxy-api.thurstons.house
# Description: Self-hosted LLM proxy behind Cloudflare Tunnel
# Enabled: true
#
# Created via:
#   curl -X POST "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/ai-gateway/custom-providers" \
#     -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
#     -H "Content-Type: application/json" \
#     -d '{
#       "name": "CLI Proxy API",
#       "slug": "cli-proxy-api",
#       "base_url": "https://cli-proxy-api.thurstons.house",
#       "description": "Self-hosted LLM proxy behind Cloudflare Tunnel",
#       "enable": true
#     }'
#
# =============================================================================
# ARCHITECTURE
# =============================================================================
#
# Request flow:
#
#   Client
#     │ Authorization: Bearer <CLI_PROXY_API_KEY>
#     ▼
#   aig.thurstons.house (Worker)
#     │ Validates API_KEY
#     │ Adds cf-aig-authorization header
#     │ Adds CF-Access-Client-Id/Secret headers
#     ▼
#   gateway.ai.cloudflare.com/v1/{account}/{gateway}/custom-cli-proxy-api/{path}
#     │ AI Gateway provides: analytics, logging, caching, rate limiting
#     │ Forwards CF-Access headers to custom provider
#     ▼
#   cli-proxy-api.thurstons.house (via Cloudflare Tunnel)
#     │ Access validates service token
#     ▼
#   Backend LLM proxy (192.168.5.235:8317)
