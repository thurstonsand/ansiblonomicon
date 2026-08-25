#!/usr/bin/env bash
# Does the state pyinfra built actually work?
set -uo pipefail
rm -f /var/log/mockapi.jsonl; systemctl restart mockapi; sleep 1

echo "### 1. heartbeat unit pings its check"
systemctl start alerting-heartbeat.service
sleep 1
grep -c 'ping/pod042-heartbeat' /var/log/mockapi.jsonl

echo "### 2. sanoid cuts snapshots on black-box, none on ark"
systemctl start sanoid.service
sleep 5
printf 'black-box snapshots: %s\n' "$(zfs list -t snapshot -H -o name 2>/dev/null | grep -c '^black-box')"
printf 'ark snapshots: %s\n' "$(zfs list -t snapshot -H -o name 2>/dev/null | grep -c '^ark')"
printf 'sanoid ExecStart wrapped: %s\n' "$(systemctl cat sanoid.service | grep -c 'hc-run pod042-sanoid')"
grep -c 'ping/pod042-sanoid' /var/log/mockapi.jsonl

echo "### 3. scrub runs under hc-run"
systemctl start 'zfs-scrub-pool@black-box.service'
sleep 8
systemctl show 'zfs-scrub-pool@black-box.service' -p Result --value
grep -o 'ping/pod042-zfs-scrub-black-box[^"]*' /var/log/mockapi.jsonl | sort | uniq -c
zpool status black-box | grep -c 'scrub repaired'

echo "### 4. zed forwards a vdev fault to Hark"
zpool offline -f black-box /var/lib/testpools/black-box-b.img
sleep 6
python3 - <<'PY'
import json
for line in open('/var/log/mockapi.jsonl'):
    rec = json.loads(line)
    if rec['kind'] == 'hark':
        body = json.loads(rec['body'])
        print('HARK title:', body['title'])
        print('HARK body head:', body['body'].splitlines()[0])
        break
else:
    print('NO HARK EVENT')
PY
zpool online black-box /var/lib/testpools/black-box-b.img; sleep 3; zpool clear black-box; zpool status -x
