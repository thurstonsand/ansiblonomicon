#!/usr/bin/env bash
set -euo pipefail

curl -fsS -X POST \
  -H "Authorization: Bearer $GITHUB_PAT" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/thurstonsand/ansiblonomicon/dispatches" \
  -d '{"event_type":"ddns-ip-changed"}'
