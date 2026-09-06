#!/bin/bash
case "$USER" in
  tsandberg) pass_var="HOMEBREW_SUDO_ASKPASS_PASS_WORK" ;;
  *) pass_var="HOMEBREW_SUDO_ASKPASS_PASS" ;;
esac

exec "$(dirname "${BASH_SOURCE[0]}")/../scripts/fnox-host" get "$pass_var"
