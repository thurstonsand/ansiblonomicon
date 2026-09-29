#!/bin/bash
case "${HOMEBREW_ANSIBLONOMICON_EXEC_PROFILE:-}:$USER" in
  omarchy:*) pass_var="OMARCHY_SUDO_PASSWORD" ;;
  *:tsandberg) pass_var="HOMEBREW_SUDO_ASKPASS_PASS_WORK" ;;
  *) pass_var="HOMEBREW_SUDO_ASKPASS_PASS" ;;
esac

launcher="$(dirname "${BASH_SOURCE[0]}")/../scripts/fnox-host"
if [[ ${HOMEBREW_ANSIBLONOMICON_EXEC_PYTHON+x} ]]; then
  exec "$HOMEBREW_ANSIBLONOMICON_EXEC_PYTHON" "$launcher" get "$pass_var"
fi
exec "$launcher" get "$pass_var"
