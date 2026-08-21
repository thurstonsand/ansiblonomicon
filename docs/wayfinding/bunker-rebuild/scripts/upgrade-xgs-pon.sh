#!/usr/bin/env bash
# Supplementary upgrade of the WAS-110 XGS-PON stick: 8311 basic v2.8.0 -> v2.8.3.
# Runs entirely from the laptop over LAN; only the download phase needs internet.
# The stick reboots mid-flash and takes the house offline for ~3-5 minutes —
# this script keeps running through the outage and verifies recovery.
#
# Usage: upgrade-xgs-pon.sh [--resume]
#   --resume  skip download/baseline/flash, go straight to waiting for the
#             stick to return and verifying (safe after a mid-run interrupt).
#
# Companion runbook for failures: ../runbooks/xgs-pon-upgrade.md

set -euo pipefail

STICK=192.168.11.1
VERSION=v2.8.3
ASSET="WAS-110_8311_firmware_mod_${VERSION}_basic.7z"
URL="https://github.com/djGrrr/8311-was-110-firmware-builder/releases/download/${VERSION}/${ASSET}"
WORK=/tmp/xgs-pon-upgrade
LOG="$WORK/upgrade.log"
SSH_OPTS=(-oHostKeyAlgorithms=+ssh-rsa -oPubkeyAcceptedKeyTypes=+ssh-rsa -oStrictHostKeyChecking=accept-new -oConnectTimeout=5)

mkdir -p "$WORK"
exec > >(tee -a "$LOG") 2>&1
echo "=== $(date -u +%FT%TZ) upgrade-xgs-pon start (args: $*) ==="

PW=$(op read 'op://agent/XGS PON/password')
stick() { sshpass -p "$PW" ssh "${SSH_OPTS[@]}" "root@$STICK" "$@"; }
stick_scp() { sshpass -p "$PW" scp -O "${SSH_OPTS[@]}" "$@"; }

wait_for() { # wait_for <label> <timeout_s> <cmd...>
  local label=$1 timeout=$2; shift 2
  local start=$SECONDS
  until "$@" >/dev/null 2>&1; do
    if (( SECONDS - start > timeout )); then
      echo "FAIL: timed out after ${timeout}s waiting for: $label"
      echo "See runbook: docs/wayfinding/bunker-rebuild/runbooks/xgs-pon-upgrade.md"
      exit 1
    fi
    sleep 5
  done
  echo "OK: $label ($((SECONDS - start))s)"
}

if [[ "${1:-}" != "--resume" ]]; then
  echo "--- Phase 0: download + extract (needs internet) ---"
  [[ -f "$WORK/$ASSET" ]] || curl -fL -o "$WORK/$ASSET" "$URL"
  # macOS Archive Utility mangles the tar; bsdtar handles 7z via libarchive
  [[ -f "$WORK/local-upgrade.tar" ]] || bsdtar -xf "$WORK/$ASSET" -C "$WORK" local-upgrade.tar
  ls -l "$WORK/local-upgrade.tar"

  echo "--- Phase 1: baseline + config capture ---"
  stick '. /lib/8311.sh; echo "active bank: $(active_fwbank)"; cat /etc/8311_version 2>/dev/null || true' \
    | tee "$WORK/baseline-bank.txt"
  stick 'fw_printenv | grep "^8311" || true' > "$WORK/baseline-8311-env.txt"
  stick 'tar czf - /etc/config 2>/dev/null' > "$WORK/baseline-etc-config.tar.gz"
  stick 'for z in /sys/class/thermal/thermal_zone*/temp; do cat $z; done' > "$WORK/baseline-temps.txt"
  echo "baseline saved to $WORK/baseline-*"

  echo "--- Phase 2: flash (INTERNET GOES DOWN HERE) ---"
  stick_scp "$WORK/local-upgrade.tar" "root@$STICK:/tmp/"
  # ssh exits nonzero when the stick reboots out from under us; that is expected
  stick 'tar xvf /tmp/local-upgrade.tar -C /tmp/ -- upgrade.sh && /tmp/upgrade.sh -y -r /tmp/local-upgrade.tar' \
    || echo "(connection dropped — expected if the stick went down to reboot)"

  echo "--- Phase 2b: wait for the reboot to actually begin ---"
  # upgrade.sh prints "Rebooting..." seconds before the stick drops; without this
  # gate, phase 3 pings the still-running old firmware and verification races.
  wait_for "stick went down" 120 sh -c "! ping -c1 -W2 $STICK"
fi

echo "--- Phase 3: wait for stick to return ---"
wait_for "stick pingable" 900 ping -c1 -W2 "$STICK"
wait_for "stick ssh up" 300 stick true

echo "--- Phase 4: verify ---"
stick '. /lib/8311.sh; echo "active bank: $(active_fwbank)"; cat /etc/8311_version 2>/dev/null || true' \
  | tee "$WORK/post-bank.txt"
if ! grep -q "2\.8\.3" "$WORK/post-bank.txt"; then
  echo "FAIL: stick is up but not reporting v2.8.3 — see runbook (bank may not have switched)"
  exit 1
fi
wait_for "PON state O5" 600 sh -c "sshpass -p \"\$PW\" ssh ${SSH_OPTS[*]} root@$STICK 'pontop -b -g s' | grep -q 'O5'"
wait_for "internet restored" 600 ping -c1 -W2 1.1.1.1
echo "--- v2.8.2+ metrics endpoint check ---"
curl -sk --max-time 5 "https://$STICK/cgi-bin/luci/8311/metrics" | head -12 || echo "(metrics endpoint not answering — non-fatal, check via luci)"

echo "=== $(date -u +%FT%TZ) upgrade complete: v2.8.3 active, PON up, internet restored ==="
