#!/usr/bin/env bash
# Fingerprint everything the alerting + zfs_maintenance segment owns.
set -uo pipefail
echo "### files (mode owner sha256 path)"
for f in /usr/local/bin/hc-run /usr/local/bin/storage-alert /usr/local/bin/zfs-scrub-pool \
         /usr/local/bin/smartd-alert /etc/alerting/hark-webhook-url \
         /etc/alerting/checks/pod042-heartbeat.url /etc/alerting/checks/pod042-sanoid.url \
         /etc/alerting/checks/pod042-zfs-scrub-ark.url /etc/alerting/checks/pod042-zfs-scrub-black-box.url \
         /etc/sanoid/sanoid.conf /etc/smartd.conf \
         /etc/systemd/system/alerting-heartbeat.service /etc/systemd/system/alerting-heartbeat.timer \
         /etc/systemd/system/sanoid.service.d/10-healthchecks.conf \
         /etc/systemd/system/zfs-scrub-pool@.service \
         /etc/systemd/system/zfs-scrub-pool@ark.timer /etc/systemd/system/zfs-scrub-pool@black-box.timer \
         /etc/zfs/zed.d/statechange-storage-alert.sh /etc/zfs/zed.d/data-storage-alert.sh \
         /etc/zfs/zed.d/scrub_finish-storage-alert.sh /etc/zfs/zed.d/resilver_finish-storage-alert.sh; do
  if [ -e "$f" ]; then
    printf '%s %s:%s %s %s\n' "$(stat -c %a "$f")" "$(stat -c %U "$f")" "$(stat -c %G "$f")" "$(sha256sum "$f" | cut -c1-16)" "$f"
  else
    printf 'MISSING %s\n' "$f"
  fi
done
echo "### directories"
for d in /etc/alerting /etc/alerting/checks /etc/sanoid /etc/systemd/system/sanoid.service.d; do
  [ -d "$d" ] && printf '%s %s:%s %s\n' "$(stat -c %a "$d")" "$(stat -c %U "$d")" "$(stat -c %G "$d")" "$d" || printf 'MISSING %s\n' "$d"
done
echo "### units (enabled/active)"
for u in alerting-heartbeat.timer sanoid.timer zfs-scrub-pool@ark.timer zfs-scrub-pool@black-box.timer smartd.service zfs-zed.service; do
  printf '%s enabled=%s active=%s\n' "$u" "$(systemctl is-enabled "$u" 2>&1)" "$(systemctl is-active "$u" 2>&1)"
done
echo "### packages"
dpkg-query -W -f '${Package} ${Status}\n' curl jq sanoid smartmontools zfs-zed 2>&1
echo "### zpool autoreplace"
for p in ark black-box; do printf '%s autoreplace=%s\n' "$p" "$(zpool get -H -o value autoreplace $p)"; done
echo "### mock checks registered"
cat /var/lib/mockapi-checks.json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(k) for k in sorted(d)]' 2>/dev/null
