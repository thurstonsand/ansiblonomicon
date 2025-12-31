#!/bin/bash
set -euo pipefail
TARGET_UID=950
TARGET_GID=544
PASSWD_ENTRY=$(getent passwd node)
CURRENT_UID=$(echo "$PASSWD_ENTRY" | cut -d: -f3)
CURRENT_GID=$(echo "$PASSWD_ENTRY" | cut -d: -f4)
GROUP_ENTRY=$(getent group node)
CURRENT_GROUP_GID=$(echo "$GROUP_ENTRY" | cut -d: -f3)
if [ "$CURRENT_UID" != "$TARGET_UID" ] || [ "$CURRENT_GID" != "$TARGET_GID" ]; then
  sed -i "s/^node:[^:]*:$CURRENT_UID:$CURRENT_GID:/node:x:$TARGET_UID:$TARGET_GID:/" /etc/passwd
fi
if [ "$CURRENT_GROUP_GID" != "$TARGET_GID" ]; then
  sed -i "s/^node:[^:]*:$CURRENT_GROUP_GID:/node:x:$TARGET_GID:/" /etc/group
fi
chown -R ${TARGET_UID}:${TARGET_GID} /var/lib/ghost/content
exec /usr/local/bin/docker-entrypoint.sh "$@"
