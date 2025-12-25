#!/bin/bash
# If SUDO_ASKPASS_PASS is set (from op run), use it
# Otherwise, fetch directly from 1Password
if [[ -n "$SUDO_ASKPASS_PASS" ]]; then
  echo "$SUDO_ASKPASS_PASS"
else
  /opt/homebrew/bin/op read "op://Private/Apple Macbook Login/password"
fi
