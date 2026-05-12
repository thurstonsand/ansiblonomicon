#!/bin/bash
case "$USER" in
  tsandberg) pass_var="HOMEBREW_SUDO_ASKPASS_PASS_WORK" ;;
  *) pass_var="HOMEBREW_SUDO_ASKPASS_PASS" ;;
esac

echo "${!pass_var}"
