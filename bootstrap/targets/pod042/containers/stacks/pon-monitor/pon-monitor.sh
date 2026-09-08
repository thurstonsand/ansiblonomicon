#!/bin/sh
# Sample the XGS-PON stick continuously and capture its volatile state the
# moment the WAN dies. The stick keeps its log in RAM, so every power cycle
# destroys the evidence for the outage that provoked it — twice now. This runs
# the capture before a human can reach behind the rack.
set -u

metrics_url="${PON_METRICS_URL:?PON_METRICS_URL is required}"
stick_host="${PON_STICK_HOST:?PON_STICK_HOST is required}"
stick_user="${PON_STICK_USER:?PON_STICK_USER is required}"
stick_password="${PON_STICK_PASSWORD:?PON_STICK_PASSWORD is required}"
probe_urls="${PON_PROBE_URLS:?PON_PROBE_URLS is required}"
sample_interval="${PON_SAMPLE_INTERVAL:?PON_SAMPLE_INTERVAL is required}"
failures_before_capture="${PON_FAILURES_BEFORE_CAPTURE:?PON_FAILURES_BEFORE_CAPTURE is required}"
samples_path="${PON_SAMPLES_PATH:?PON_SAMPLES_PATH is required}"
samples_max_bytes="${PON_SAMPLES_MAX_BYTES:?PON_SAMPLES_MAX_BYTES is required}"
samples_keep="${PON_SAMPLES_KEEP:?PON_SAMPLES_KEEP is required}"
captures_dir="${PON_CAPTURES_DIR:?PON_CAPTURES_DIR is required}"
spool_dir="${PON_SPOOL_DIR:?PON_SPOOL_DIR is required}"
spool_keep="${PON_SPOOL_KEEP:?PON_SPOOL_KEEP is required}"
hark_webhook_url="${PON_HARK_WEBHOOK_URL:?PON_HARK_WEBHOOK_URL is required}"
healthcheck_ping_url="${PON_HEALTHCHECK_PING_URL:?PON_HEALTHCHECK_PING_URL is required}"
healthcheck_interval="${PON_HEALTHCHECK_INTERVAL:?PON_HEALTHCHECK_INTERVAL is required}"

mkdir -p "$(dirname "$samples_path")" "$captures_dir" "$spool_dir"

log() {
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"
}

# HTTPS rather than ICMP: an unprivileged container cannot count on raw sockets,
# and a completed TLS handshake is the honest test of a usable WAN anyway. One
# reachable target is enough — a single provider having a bad day is not an
# outage.
probe_wan() {
  for url in $probe_urls; do
    if curl -sk --max-time 5 -o /dev/null "$url"; then
      return 0
    fi
  done
  return 1
}

sample_metrics() {
  curl -sk --max-time 5 "$metrics_url" 2>/dev/null
}

# An alert about a dead WAN cannot travel over that WAN. Spool it to disk and
# let the recovery deliver it; the alternative is a notification that only ever
# fires when it is not needed.
queue_alert() {
  jq -nc --arg title "$1" --arg body "$2" '{title: $title, body: $body}' \
    >"${spool_dir}/$(date -u +%Y%m%dT%H%M%SZ)-$$.json"

  # A long Hark outage must not fill the pool; the captures themselves are the
  # durable record, so drop the oldest alerts rather than the newest.
  spooled="$(ls "$spool_dir" | wc -l)"
  if [ "$spooled" -gt "$spool_keep" ]; then
    ls "$spool_dir" | sort | head -n "$((spooled - spool_keep))" | while read -r stale; do
      rm -f "${spool_dir}/${stale}"
    done
  fi
}

# Oldest first, and stop at the first failure so the queue keeps its order and
# the loop keeps its cadence.
flush_alerts() {
  for payload in $(ls "$spool_dir" 2>/dev/null | sort); do
    if curl -fsS --max-time 15 \
      -H 'Content-Type: application/json' \
      -H "Idempotency-Key: ${payload%.json}" \
      --data-binary "@${spool_dir}/${payload}" -o /dev/null \
      "$hark_webhook_url"; then
      rm -f "${spool_dir}/${payload}"
      log "delivered alert ${payload}"
    else
      log "alert ${payload} still undelivered"
      return 1
    fi
  done
}

# One capture per event. Everything here is read-only on the stick, and every
# command carries its own deadline: a wedged stick must not wedge the monitor.
capture() {
  reason="$1"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  path="${captures_dir}/${stamp}.log"

  {
    echo "== capture $stamp"
    echo "== reason: $reason"
    echo "== monitor host: $(hostname)"
    echo
    echo "== metrics endpoint"
    sample_metrics || echo "(unreachable)"
    echo
    echo "== probe timing"
    for url in $probe_urls; do
      printf '%s ' "$url"
      curl -sk --max-time 20 -o /dev/null \
        -w 'connect=%{time_connect}s tls=%{time_appconnect}s total=%{time_total}s code=%{http_code}\n' \
        "$url" 2>&1 || echo "failed"
    done
    echo
    echo "== stick"
    sshpass -p "$stick_password" ssh \
      -o HostKeyAlgorithms=+ssh-rsa \
      -o PubkeyAcceptedKeyTypes=+ssh-rsa \
      -o PubkeyAuthentication=no \
      -o PreferredAuthentications=password \
      -o NumberOfPasswordPrompts=1 \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o LogLevel=ERROR \
      -o ConnectTimeout=10 \
      "${stick_user}@${stick_host}" '
        uptime; cat /proc/uptime
        echo "-- reset cause"; fw_printenv 2>/dev/null | grep -i rst_cause
        echo "-- thermal"; for z in /sys/class/thermal/thermal_zone*; do printf "%s " "$(cat $z/type)"; cat $z/temp; done
        echo "-- ploam"; pontop -b -g s
        echo "-- optics"; pontop -b -g "Optical Interface Status"
        echo "-- alarms"; pontop -b -g w
        echo "-- fec"; pontop -b -g f
        echo "-- gtc"; pontop -b -g t
        echo "-- host link"; ethtool eth0_0
        echo "-- dmesg"; dmesg | tail -100
        echo "-- logread"; logread | tail -200
      ' 2>&1
  } >"$path"

  log "captured $path ($reason)"

  queue_alert "PON event captured" \
    "$(printf 'reason: %s\ncapture: %s\n\n%s' "$reason" "$path" "$(head -c 3000 "$path")")"
}

# Keep the sample log bounded without dragging logrotate into the image.
rotate_samples() {
  size="$(wc -c <"$samples_path" 2>/dev/null || echo 0)"
  [ "$size" -lt "$samples_max_bytes" ] && return 0

  index="$samples_keep"
  while [ "$index" -gt 1 ]; do
    previous=$((index - 1))
    [ -f "${samples_path}.${previous}" ] && mv "${samples_path}.${previous}" "${samples_path}.${index}"
    index="$previous"
  done
  mv "$samples_path" "${samples_path}.1"
}

consecutive_failures=0
captured_this_event=0
last_healthcheck=0

log "sampling ${metrics_url} every ${sample_interval}s; probing ${probe_urls}"

while true; do
  now="$(date -u +%s)"

  metrics="$(sample_metrics)"
  if [ -n "$metrics" ]; then
    stick_reachable=true
  else
    stick_reachable=false
    metrics='{}'
  fi

  if probe_wan; then
    wan_up=true
    consecutive_failures=0
    if [ "$captured_this_event" -eq 1 ]; then
      log "wan recovered; re-arming capture"
      captured_this_event=0
    fi
    flush_alerts
  else
    wan_up=false
    consecutive_failures=$((consecutive_failures + 1))
  fi

  echo "$metrics" | jq -c \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --argjson wan_up "$wan_up" \
    --argjson stick_reachable "$stick_reachable" \
    --argjson failures "$consecutive_failures" \
    '{ts: $ts, wan_up: $wan_up, stick_reachable: $stick_reachable, consecutive_failures: $failures} + .' \
    >>"$samples_path"
  rotate_samples

  if [ "$consecutive_failures" -ge "$failures_before_capture" ] && [ "$captured_this_event" -eq 0 ]; then
    captured_this_event=1
    capture "wan down for ${consecutive_failures} consecutive probes"
  fi

  # The ping only lands when the WAN is up, which is the point: a monitor that
  # cannot report is indistinguishable from a monitor that is not running. The
  # interval advances either way, so an outage costs one failed ping per period
  # instead of one per sample.
  if [ $((now - last_healthcheck)) -ge "$healthcheck_interval" ]; then
    last_healthcheck="$now"
    curl -fsS --max-time 10 -o /dev/null "$healthcheck_ping_url" ||
      log "healthcheck ping failed"
  fi

  sleep "$sample_interval"
done
