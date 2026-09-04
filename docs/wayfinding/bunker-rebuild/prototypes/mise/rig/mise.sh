#!/usr/bin/env bash
# mise converge wrapper: rig-only overrides for the mocked endpoints.
set -uo pipefail
cd /home/thurston/Develop/ansiblonomicon/docs/wayfinding/bunker-rebuild/prototypes/mise || exit 1
export PATH="$HOME/.local/bin:$PATH"
export ALERTING_HEALTHCHECKS_API_URL=http://127.0.0.1:8099/api/v3/checks/
export HEALTHCHECKS_API_KEY=mock-api-key
export HARK_WEBHOOK_URL=http://127.0.0.1:8099/hark
exec mise run "$@"
