#!/bin/sh
set -eu

credentials=/etc/ansiblonomicon/samba/credentials

if smbclient -L localhost --authentication-file="$credentials" --max-protocol=SMB3 >/dev/null 2>&1; then
  exit
fi

password=$(sed -n 's/^password = //p' "$credentials")
if [ -z "$password" ]; then
  echo "Samba credential file has no password" >&2
  exit 1
fi

printf '%s\n%s\n' "$password" "$password" | smbpasswd -s -a thurstonsand >/dev/null
smbclient -L localhost --authentication-file="$credentials" --max-protocol=SMB3 >/dev/null
