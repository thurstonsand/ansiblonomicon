#!/usr/bin/env bash
# Push one notification to Thurston's phone. Usage: notify.sh [--url <link>] <body...>
# Body may also arrive on stdin. Hark is the delivery backend; swap it out here.
set -uo pipefail

usage() {
  echo "usage: notify.sh [--url <link>] <body...>" >&2
  exit 64
}

tap_url=""
if [[ ${1:-} == --url ]]; then
  tap_url="${2:-}"
  [[ -n $tap_url ]] || usage
  shift 2
fi

body="$*"
if [[ -z $body && ! -t 0 ]]; then
  body="$(cat)"
fi
[[ -n $body ]] || usage

webhook_url="$("$HOME/.local/bin/fnox-host" get HARK_WEBHOOK_URL_2B)" || exit 1
[[ -n $webhook_url ]] || { echo "notify: empty webhook credential" >&2; exit 1; }

payload="$(jq -nc \
  --arg body "${body:0:2000}" \
  --arg url "$tap_url" \
  '{body: $body} + (if $url == "" then {} else {url: $url} end)')"

# Curl reads the credential URL from stdin, never from its argument list.
if ! printf '%s' "$webhook_url" | jq -Rrs '"url = " + tojson' |
  curl -fs --config - --max-time 15 --retry 2 --retry-delay 3 \
    -H 'Content-Type: application/json' \
    -H "Idempotency-Key: $(date +%s)-$$" \
    --data-binary "$payload" \
    -o /dev/null; then
  echo "notify: delivery failed: ${body:0:60}" >&2
  exit 1
fi
