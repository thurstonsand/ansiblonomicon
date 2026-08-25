#!/usr/bin/env bash
set -uo pipefail
cd /home/thurston
t() { local label="$1"; shift; local s=$(date +%s%3N); "$@" > /tmp/bench.log 2>&1; local rc=$?; local e=$(date +%s%3N)
      printf '%-28s %6d ms rc=%d\n' "$label" "$((e - s))" "$rc"; }

sudo /usr/local/sbin/reset.sh > /dev/null
echo "== ansible (tags alerting,sanoid,scrub,smartd,zed)"
t "full converge" ./converge.sh
t "no-op re-run" ./converge.sh
t "--check --diff" ./converge.sh --check
t "partial: --tags scrub" ./converge-tags.sh scrub
sudo /usr/local/sbin/fingerprint.sh > /tmp/fp-ansible.txt

sudo /usr/local/sbin/reset.sh > /dev/null
echo "== pyinfra"
t "full converge" ./pyi.sh deploy.py -y
t "no-op re-run" ./pyi.sh deploy.py -y
t "--dry --diff" ./pyi.sh deploy.py --dry --diff
t "partial: parts/scrub.py" ./pyi.sh parts/scrub.py -y
sudo /usr/local/sbin/fingerprint.sh > /tmp/fp-pyinfra.txt

echo "== fingerprint diff (ansible vs pyinfra)"
diff /tmp/fp-ansible.txt /tmp/fp-pyinfra.txt && echo "IDENTICAL"
