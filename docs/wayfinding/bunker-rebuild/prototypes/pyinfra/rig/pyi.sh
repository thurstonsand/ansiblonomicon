#!/usr/bin/env bash
# pyinfra converge wrapper: rig-only overrides for the mocked endpoints.
set -uo pipefail
cd /home/thurston/Develop/ansiblonomicon/docs/wayfinding/bunker-rebuild/prototypes/pyinfra || exit 1
export PATH="$HOME/.local/bin:$PATH"
exec uv run pyinfra inventory.py "$@" \
  --data alerting_healthchecks_api_url=http://127.0.0.1:8099/api/v3/checks/ \
  --data alerting_healthchecks_api_key=mock-api-key \
  --data alerting_hark_webhook_url=http://127.0.0.1:8099/hark
