# shellcheck shell=bash
# Register one Healthchecks check and drop its ping URL where the job's unit can
# load it as a systemd credential. This is check.yml, and it is the reusable
# half of the alerting unit: zfs-maintenance sources this file rather than
# calling a mise task, because a task invocation cannot return a value and a
# nested `mise run` per check costs a process.
#
#   source "$ALERTING_CHECK_LIB"
#   alerting::check pod042-sanoid "0 * * * *" 1800
#
# A `unique` POST both creates and updates, returning 201 only on create, so
# reading the current state first is the only way to notice schedule, timezone
# or grace drift.

alerting::check() {
  local check="$1" schedule="$2" grace="$3" install_url="${4:-true}"
  local api="$ALERTING_HEALTHCHECKS_API_URL" key="$ALERTING_HEALTHCHECKS_API_KEY"
  local existing desired_reason="" response ping_url

  existing="$(curl -fsS --max-time 10 -H "X-Api-Key: ${key}" "${api}?slug=${check}" |
    jq -c --arg slug "$check" '[.checks[]? | select(.slug == $slug)] | first // {}')"

  if [[ "$existing" == "{}" ]]; then
    desired_reason=create
  else
    local current_schedule current_tz current_grace
    current_schedule="$(jq -r '.schedule // ""' <<<"$existing")"
    current_tz="$(jq -r '.tz // ""' <<<"$existing")"
    current_grace="$(jq -r '.grace // -1' <<<"$existing")"
    [[ "$current_schedule" == "$schedule" ]] || desired_reason="schedule ${current_schedule} -> ${schedule}"
    [[ -n "$desired_reason" ]] ||
      [[ "$current_tz" == "$ALERTING_HEALTHCHECKS_TIMEZONE" ]] ||
      desired_reason="tz ${current_tz} -> ${ALERTING_HEALTHCHECKS_TIMEZONE}"
    [[ -n "$desired_reason" ]] ||
      [[ "$current_grace" == "$grace" ]] ||
      desired_reason="grace ${current_grace} -> ${grace}"
  fi

  if [[ -z "$desired_reason" ]]; then
    reconcile::ok "check $check"
    ping_url="$(jq -r '.ping_url' <<<"$existing")"
  elif reconcile::check; then
    reconcile::changed "check $check ($desired_reason)"
    ping_url="$(jq -r '.ping_url // ""' <<<"$existing")"
  else
    response="$(jq -nc \
      --arg name "$check" --arg schedule "$schedule" \
      --arg tz "$ALERTING_HEALTHCHECKS_TIMEZONE" --argjson grace "$grace" \
      '{name: $name, slug: $name, schedule: $schedule, tz: $tz, grace: $grace,
        channels: "*", unique: ["name"]}' |
      curl -fsS --max-time 10 -X POST -H "X-Api-Key: ${key}" \
        -H 'Content-Type: application/json' --data-binary @- "$api")" ||
      reconcile::failed "check $check"
    ping_url="$(jq -r '.ping_url' <<<"$response")"
    reconcile::changed "check $check ($desired_reason)"
  fi

  [[ "$install_url" == "true" && -n "$ping_url" ]] || return 0
  printf '%s\n' "$ping_url" |
    reconcile::file "${ALERTING_STATE_DIR}/checks/${check}.url" 0600 root root
}
