#!/bin/bash
set -euo pipefail

# BetterTouchTool runs actions with a stripped environment.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

PRIMARY_HOST="openclaw"
SECONDARY_HOST="truenas"

pass_through_option_v() {
  osascript -e 'tell application "System Events" to keystroke "v" using option down'
}

paste_text_via_cmd_v() {
  local text="$1"
  osascript - "$text" <<'APPLESCRIPT'
on run argv
  set textToPaste to item 1 of argv
  set oldClipboard to the clipboard
  set the clipboard to textToPaste
  tell application "System Events"
    keystroke "v" using command down
  end tell
  delay 0.05
  set the clipboard to oldClipboard
end run
APPLESCRIPT
}

notify_error() {
  local message="$1"
  osascript -e "display notification \"${message}\" with title \"Paste Error\" sound name \"Basso\""
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    notify_error "Missing dependency: ${cmd}"
    exit 1
  fi
}

for cmd in osascript pgrep ssh scp pngpaste; do
  require_cmd "$cmd"
done

resolve_transfer_target() {
  local host="$1"
  printf '%s|%s' "$host" 'ssh-config'
}

has_active_ssh_to_host() {
  local host="$1"
  pgrep -qf "ssh.*${host}"
}

select_remote_host() {
  if has_active_ssh_to_host "$PRIMARY_HOST"; then
    printf '%s' "$PRIMARY_HOST"
    return 0
  fi

  if has_active_ssh_to_host "$SECONDARY_HOST"; then
    printf '%s' "$SECONDARY_HOST"
    return 0
  fi

  return 1
}

if ! REMOTE_HOST=$(select_remote_host); then
  pass_through_option_v
  exit 0
fi

IFS='|' read -r REMOTE_TARGET REMOTE_TARGET_MODE <<<"$(resolve_transfer_target "$REMOTE_HOST")"

SSH_OPTS=(-o ConnectTimeout=10)

# Check clipboard for image data and extract
TMPFILE=$(mktemp /tmp/clipboard-XXXXXX.png)
ERRFILE=$(mktemp /tmp/btt-paste-image-err-XXXXXX.log)
trap 'rm -f "$TMPFILE" "$ERRFILE"' EXIT

if ! pngpaste "$TMPFILE" 2>/dev/null; then
  pass_through_option_v
  exit 0
fi

# Transfer to remote host (ephemeral file in /tmp).
REMOTE_PATH=$(ssh "${SSH_OPTS[@]}" "$REMOTE_TARGET" "mktemp /tmp/btt-clipboard-XXXXXXXX.png" 2>"$ERRFILE" || true)

if [ -z "$REMOTE_PATH" ]; then
  error_line=$(head -n1 "$ERRFILE" | tr -d '\r' || true)
  if [ -n "$error_line" ]; then
    notify_error "Remote temp file failed: ${error_line}"
  else
    notify_error "Remote temp file failed"
  fi
  exit 1
fi

if scp -q "${SSH_OPTS[@]}" "$TMPFILE" "${REMOTE_TARGET}:${REMOTE_PATH}" 2>>"$ERRFILE"; then
  paste_text_via_cmd_v "$REMOTE_PATH"
  osascript -e "display notification \"${REMOTE_PATH}\" with title \"Image Pasted\" subtitle \"Transferred to ${REMOTE_HOST} (${REMOTE_TARGET_MODE})\""
else
  error_line=$(head -n1 "$ERRFILE" | tr -d '\r' || true)
  if [ -n "$error_line" ]; then
    notify_error "SCP transfer failed: ${error_line}"
  else
    notify_error "SCP transfer failed"
  fi
  exit 1
fi
