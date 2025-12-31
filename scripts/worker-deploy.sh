#!/usr/bin/env bash
# Deploy llms Worker via Wrangler with secret management
#
# Usage: ./scripts/worker-deploy.sh [--force-secret]
#
# Deploys the worker and ensures API_KEY secret exists.
# Use --force-secret to update the secret even if it exists.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
WORKER_DIR="$ROOT_DIR/wrangler/llms"

FORCE_SECRET=false
if [[ "${1:-}" == "--force-secret" ]]; then
  FORCE_SECRET=true
fi

cd "$WORKER_DIR"

echo "Deploying llms worker..."
wrangler deploy

echo ""
echo "Checking API_KEY secret..."

# List secrets and check if API_KEY exists
if wrangler secret list 2>/dev/null | grep -q "API_KEY"; then
  if $FORCE_SECRET; then
    echo "Updating API_KEY secret (--force-secret)..."
    echo "$CLI_PROXY_API_KEY" | wrangler secret put API_KEY
  else
    echo "API_KEY secret already exists (use --force-secret to update)"
  fi
else
  echo "Creating API_KEY secret..."
  echo "$CLI_PROXY_API_KEY" | wrangler secret put API_KEY
fi

echo ""
echo "Done! Worker deployed to https://llms.thurstons.house"
