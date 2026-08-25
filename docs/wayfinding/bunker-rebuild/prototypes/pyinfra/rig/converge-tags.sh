#!/usr/bin/env bash
set -uo pipefail
TAGS="$1"; shift
cd /home/thurston/Develop/ansiblonomicon/ansible || exit 1
export PATH="$HOME/.local/bin:$PATH"
export HARK_WEBHOOK_URL=http://127.0.0.1:8099/hark
export HEALTHCHECKS_API_KEY=mock-api-key
exec uv run ansible-playbook -i inventory/targets/pod042.yml playbooks/pod042.yml --diff \
  -e pod042_allow_virtual=true \
  -e alerting_healthchecks_api_url=http://127.0.0.1:8099/api/v3/checks/ \
  -e alerting_healthchecks_api_key=mock-api-key \
  -e alerting_hark_webhook_url=http://127.0.0.1:8099/hark \
  --tags "$TAGS" "$@"
