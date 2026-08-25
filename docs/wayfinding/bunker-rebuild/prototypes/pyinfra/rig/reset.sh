#!/usr/bin/env bash
# Return the rig to the state it had before either tool ran: no segment
# packages, no segment files, no registered checks.
set -uo pipefail
systemctl disable --now alerting-heartbeat.timer sanoid.timer \
  'zfs-scrub-pool@ark.timer' 'zfs-scrub-pool@black-box.timer' smartd zfs-zed >/dev/null 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get -qq purge -y sanoid smartmontools zfs-zed jq >/dev/null 2>&1
apt-get -qq autoremove -y >/dev/null 2>&1
rm -rf /etc/alerting /etc/sanoid /etc/systemd/system/sanoid.service.d \
  /etc/systemd/system/alerting-heartbeat.service /etc/systemd/system/alerting-heartbeat.timer \
  /etc/systemd/system/zfs-scrub-pool@.service /etc/systemd/system/'zfs-scrub-pool@ark.timer' \
  /etc/systemd/system/'zfs-scrub-pool@black-box.timer' \
  /usr/local/bin/hc-run /usr/local/bin/storage-alert /usr/local/bin/zfs-scrub-pool \
  /usr/local/bin/smartd-alert /etc/smartd.conf /etc/zfs/zed.d/*-storage-alert.sh
systemctl daemon-reload
zpool set autoreplace=off ark
rm -f /var/lib/mockapi-checks.json /var/log/mockapi.jsonl
systemctl restart mockapi
apt-get -qq update >/dev/null 2>&1
echo "reset done"
