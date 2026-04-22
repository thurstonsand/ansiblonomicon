#!/usr/bin/env bash
set -euo pipefail

input=$(cat)

agent_id=$(echo "$input" | jq -r '.agent_id // empty')
[[ -z "$agent_id" ]] || exit 0

transcript=$(echo "$input" | jq -r '.transcript_path // empty')
session_id=$(echo "$input" | jq -r '.session_id // empty')
[[ -n "$transcript" && -f "$transcript" ]] || exit 0

# Already titled — nothing to do
if jq -e 'select(.type == "custom-title")' "$transcript" >/dev/null 2>&1; then
  exit 0
fi

# Drop everything before the first user message (startup noise: attachments, hooks, snapshots)
context=$(jq -cs '
  (. | to_entries | map(select(.value.type == "user")) | .[0].key // length) as $start
  | .[$start:][]
' "$transcript")
[[ -n "$context" ]] || exit 0

# Generate title via Anthropic API (Sonnet)
model="${ANTHROPIC_DEFAULT_SONNET_MODEL:-$ANTHROPIC_DEFAULT_HAIKU_MODEL}"

response=$(curl -s --max-time 10 \
  -H "Authorization: Bearer ${ANTHROPIC_API_KEY}" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -H "User-Agent: claude" \
  "${ANTHROPIC_BASE_URL:-https://api.anthropic.com}/v1/messages" \
  -d "$(jq -n --arg ctx "$context" --arg model "$model" '{
    model: $model,
    max_tokens: 60,
    messages: [{role: "user", content: ("Name this coding session (under 80 chars). Be specific to what was discussed. Your exact output will be displayed to the user, so make sure that it contains ONLY the title itself and nothing else.\n\n" + $ctx)}]
  }')" 2>/dev/null)

title=$(echo "$response" | jq -r '.content[0].text // empty' 2>/dev/null)
[[ -n "$title" ]] || exit 0

# Signal for next UserPromptSubmit to pick up via sessionTitle API
mkdir -p /tmp/claude-session-titles
printf '%s' "$title" >"/tmp/claude-session-titles/${session_id}.txt"

exit 0
