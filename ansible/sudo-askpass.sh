#!/bin/bash
case "$USER" in
  tsandberg) pass_var="SUDO_ASKPASS_PASS_WORK" ;;
  *)         pass_var="SUDO_ASKPASS_PASS" ;;
esac

echo "${!pass_var}"
