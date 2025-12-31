#!/usr/bin/env bash
# Deploy aig Worker via Wrangler with secret management
#
# Usage: ./scripts/aig-deploy.sh [--force-secret]
#
# Deploys the worker and ensures secrets exist.
# Use --force-secret to update secrets even if they exist.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
WORKER_DIR="$ROOT_DIR/wrangler/aig"

FORCE_SECRET=false
if [[ "${1:-}" == "--force-secret" ]]; then
  FORCE_SECRET=true
fi

cd "$WORKER_DIR"

echo "Deploying aig worker..."
wrangler deploy

echo ""
echo "Checking secrets..."

update_secret() {
  local name="$1"
  local value="$2"

  if wrangler secret list 2>/dev/null | grep -q "$name"; then
    if $FORCE_SECRET; then
      echo "Updating $name secret (--force-secret)..."
      echo "$value" | wrangler secret put "$name"
    else
      echo "$name secret already exists (use --force-secret to update)"
    fi
  else
    echo "Creating $name secret..."
    echo "$value" | wrangler secret put "$name"
  fi
}

update_secret "API_KEY" "$CLI_PROXY_API_KEY"
update_secret "AIG_TOKEN" "$CLOUDFLARE_AI_GATEWAY_API_TOKEN"
update_secret "CF_ACCESS_CLIENT_ID" "$CF_ACCESS_CLIENT_ID"
update_secret "CF_ACCESS_CLIENT_SECRET" "$CF_ACCESS_CLIENT_SECRET"

echo ""
echo "Done! Worker deployed to https://aig.thurstons.house"
