#!/usr/bin/env bash
# Paired timings for all three tools, same VM, same minute, each starting from
# an identical reset. Ansible and pyinfra wrappers come from the pyinfra
# prototype's rig; only the mise column is new.
set -uo pipefail
cd /home/thurston || exit 1
proto=/home/thurston/Develop/ansiblonomicon/docs/wayfinding/bunker-rebuild/prototypes

t() {
  local label="$1"
  shift
  local start end rc
  start=$(date +%s%3N)
  "$@" >/tmp/bench.log 2>&1
  rc=$?
  end=$(date +%s%3N)
  printf '%-28s %6d ms rc=%d\n' "$label" "$((end - start))" "$rc"
}

sudo /usr/local/sbin/reset.sh >/dev/null
echo "== ansible (tags alerting,sanoid,scrub,smartd,zed)"
t "full converge" ./converge.sh
t "no-op re-run" ./converge.sh
t "--check --diff" ./converge.sh --check
t "partial: --tags scrub" ./converge-tags.sh scrub
sudo /usr/local/sbin/fingerprint.sh | tee /tmp/fp-ansible.txt >/dev/null

sudo /usr/local/sbin/reset.sh >/dev/null
echo "== pyinfra"
t "full converge" bash "$proto/pyinfra/rig/pyi.sh" deploy.py -y
t "no-op re-run" bash "$proto/pyinfra/rig/pyi.sh" deploy.py -y
t "--dry --diff" bash "$proto/pyinfra/rig/pyi.sh" deploy.py --dry --diff
t "partial: parts/scrub.py" bash "$proto/pyinfra/rig/pyi.sh" parts/scrub.py -y
sudo /usr/local/sbin/fingerprint.sh | tee /tmp/fp-pyinfra.txt >/dev/null

sudo /usr/local/sbin/reset.sh >/dev/null
echo "== mise"
t "full converge" "$proto/mise/rig/mise.sh" converge
t "no-op re-run" "$proto/mise/rig/mise.sh" converge
t "plan (RECONCILE_CHECK=1)" "$proto/mise/rig/mise.sh" plan
t "mise run --dry-run" "$proto/mise/rig/mise.sh" --dry-run converge
t "partial: :scrub" "$proto/mise/rig/mise.sh" //units/zfs-maintenance:scrub
sudo /usr/local/sbin/fingerprint.sh | tee /tmp/fp-mise.txt >/dev/null

echo "== fingerprint diff (ansible vs pyinfra)"
diff /tmp/fp-ansible.txt /tmp/fp-pyinfra.txt && echo IDENTICAL
echo "== fingerprint diff (ansible vs mise)"
diff /tmp/fp-ansible.txt /tmp/fp-mise.txt && echo IDENTICAL
