# =============================================================================
# Cloudflare AI Gateway Configuration (Manual Setup - Not Terraform Managed)
# =============================================================================
#
# AI Gateway is not yet available as a Terraform resource as of provider v5.15.
# This file documents the manual configuration for future migration.
#
# When `cloudflare_ai_gateway` becomes available, uncomment and adapt below.
#
# =============================================================================
# GATEWAY SETUP (via Dashboard: AI > AI Gateway)
# =============================================================================
#
# Gateway Name: llms
# Gateway ID: llms
# Authentication: ENABLED (cf-aig-authorization header required)
# Auth Token: Stored in 1Password at "Cloudflare/ai gateway/api token"
#
# =============================================================================
# CUSTOM PROVIDER (via API)
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
#     │ Authorization: Bearer <LLM_API_KEY>
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
