# shellcheck shell=bash
# The reconciliation runtime mise does not ship.
#
# Every property that Ansible and pyinfra give away — idempotency, change
# reporting, check mode, handlers, diffs — is implemented here, once, and every
# unit task earns it by calling these functions instead of running commands
# directly. Sourced, never executed:
#
#   source "$RECONCILE_LIB"
#   reconcile::begin alerting
#   reconcile::template "$MISE_TASK_DIR/../templates/hc-run.j2" /usr/local/bin/hc-run 0755 root root
#   reconcile::flush
#
# RECONCILE_CHECK=1 turns every mutation into a report. RECONCILE_LEDGER
# collects one line per resource so a single summary can be printed after a run
# that spanned a dozen separate task processes.

set -uo pipefail

RECONCILE_UNIT="${RECONCILE_UNIT:-unknown}"
_reconcile_handlers=()

reconcile::begin() {
  RECONCILE_UNIT="$1"
}

reconcile::check() {
  [[ "${RECONCILE_CHECK:-0}" == "1" ]]
}

reconcile::sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

reconcile::_record() {
  local state="$1" resource="$2"
  if [[ -n "${RECONCILE_LEDGER:-}" && -w "${RECONCILE_LEDGER}" ]]; then
    printf '%s\t%s\t%s\n' "$state" "$RECONCILE_UNIT" "$resource" >>"$RECONCILE_LEDGER"
  fi
}

reconcile::ok() {
  reconcile::_record ok "$1"
}

reconcile::changed() {
  reconcile::_record changed "$1"
  if reconcile::check; then
    printf '  would change: %s\n' "$1"
  else
    printf '  changed: %s\n' "$1"
  fi
}

# Aborts the task. A shell function that only returns non-zero would leave the
# script running and the task exiting 0, and mise would call the run a success —
# `set -e` is not an option here because every primitive returns non-zero for
# "this differs" as well as for "this broke".
reconcile::failed() {
  reconcile::_record failed "$1"
  printf '  FAILED: %s\n' "$1" >&2
  exit 1
}

# --- files ------------------------------------------------------------------

# Content arrives on stdin. Returns 0 always; sets RECONCILE_LAST_CHANGED so a
# caller can drive a handler off this one resource.
reconcile::file() {
  local dest="$1" mode="$2" owner="$3" group="$4"
  local tmp action=""
  tmp="$(mktemp)"
  cat >"$tmp"

  if ! reconcile::sudo test -e "$dest"; then
    action=create
  elif ! reconcile::sudo cmp -s "$tmp" "$dest"; then
    action=content
  elif ! reconcile::attrs_match "$dest" "$mode" "$owner" "$group"; then
    action=attrs
  fi

  if [[ -z "$action" ]]; then
    RECONCILE_LAST_CHANGED=0
    reconcile::ok "$dest"
    rm -f "$tmp"
    return 0
  fi

  RECONCILE_LAST_CHANGED=1
  if reconcile::check; then
    reconcile::changed "$dest ($action)"
    if [[ "$action" == content ]]; then
      reconcile::sudo diff -u "$dest" "$tmp" | sed 's/^/    /'
    fi
    rm -f "$tmp"
    return 0
  fi

  reconcile::sudo install -o "$owner" -g "$group" -m "$mode" "$tmp" "$dest"
  rm -f "$tmp"
  reconcile::changed "$dest ($action)"
}

# Render a Jinja template through the pinned minijinja-cli. Host facts come from
# the JSON sidecar, unit defaults from the environment (as ENV), and per-item
# values from trailing -D flags.
reconcile::template() {
  local template="$1" dest="$2" mode="$3" owner="$4" group="$5"
  shift 5
  local rendered
  # --py-compat for `.items()`, --trim-blocks because Ansible sets it, --strict
  # so an undefined variable is a failure rather than an empty string.
  if ! rendered="$(minijinja-cli --strict --trim-blocks --py-compat --env \
    "$template" ${RECONCILE_DEFAULTS:+"$RECONCILE_DEFAULTS"} "$RECONCILE_FACTS" "$@")"; then
    reconcile::failed "render $template"
  fi
  printf '%s\n' "$rendered" | reconcile::file "$dest" "$mode" "$owner" "$group"
}

# `stat` prints 644 where the caller writes 0644, so the comparison is numeric.
reconcile::attrs_match() {
  local path="$1" mode="$2" owner="$3" group="$4"
  local current_mode current_owner current_group
  read -r current_mode current_owner current_group < <(reconcile::sudo stat -c '%a %U %G' "$path")
  [[ $((8#$current_mode)) -eq $((8#$mode)) &&
    "$current_owner" == "$owner" && "$current_group" == "$group" ]]
}

reconcile::dir() {
  local path="$1" mode="$2" owner="$3" group="$4"
  if reconcile::sudo test -d "$path" && reconcile::attrs_match "$path" "$mode" "$owner" "$group"; then
    RECONCILE_LAST_CHANGED=0
    reconcile::ok "$path/"
    return 0
  fi
  RECONCILE_LAST_CHANGED=1
  reconcile::check && {
    reconcile::changed "$path/ (directory)"
    return 0
  }
  reconcile::sudo install -d -o "$owner" -g "$group" -m "$mode" "$path"
  reconcile::changed "$path/ (directory)"
}

reconcile::absent() {
  local path="$1"
  if ! reconcile::sudo test -e "$path" && ! reconcile::sudo test -L "$path"; then
    reconcile::ok "absent $path"
    return 0
  fi
  reconcile::check && {
    reconcile::changed "remove $path"
    return 0
  }
  reconcile::sudo rm -rf -- "$path"
  reconcile::changed "remove $path"
}

# --- packages ---------------------------------------------------------------

reconcile::apt() {
  local missing=() pkg
  for pkg in "$@"; do
    if ! dpkg-query -W -f '${Status}' "$pkg" 2>/dev/null | grep -q '^install ok installed$'; then
      missing+=("$pkg")
    fi
  done
  if [[ ${#missing[@]} -eq 0 ]]; then
    reconcile::ok "apt $*"
    return 0
  fi
  reconcile::check && {
    reconcile::changed "apt install ${missing[*]}"
    return 0
  }
  if ! reconcile::sudo env DEBIAN_FRONTEND=noninteractive apt-get -qq install -y "${missing[@]}" >/dev/null; then
    reconcile::failed "apt install ${missing[*]}"
  fi
  reconcile::changed "apt install ${missing[*]}"
}

# --- systemd ----------------------------------------------------------------

reconcile::unit() {
  local unit="$1" changed=0
  if [[ "$(systemctl is-enabled "$unit" 2>/dev/null)" != "enabled" ]]; then
    changed=1
  fi
  if [[ "$(systemctl is-active "$unit" 2>/dev/null)" != "active" ]]; then
    changed=1
  fi
  if [[ "$changed" -eq 0 ]]; then
    reconcile::ok "unit $unit"
    return 0
  fi
  reconcile::check && {
    reconcile::changed "unit $unit (enable+start)"
    return 0
  }
  reconcile::sudo systemctl enable --now "$unit" >/dev/null 2>&1
  reconcile::changed "unit $unit (enable+start)"
}

# The handler analog. Notifications collapse by name the way Ansible's do; a
# flush at the end of the task runs each at most once.
reconcile::notify() {
  local handler="$1" existing
  for existing in ${_reconcile_handlers[@]+"${_reconcile_handlers[@]}"}; do
    [[ "$existing" == "$handler" ]] && return 0
  done
  _reconcile_handlers+=("$handler")
}

reconcile::notify_if_changed() {
  [[ "${RECONCILE_LAST_CHANGED:-0}" == "1" ]] && reconcile::notify "$1"
  return 0
}

reconcile::flush() {
  local handler
  for handler in ${_reconcile_handlers[@]+"${_reconcile_handlers[@]}"}; do
    reconcile::check && {
      reconcile::changed "handler $handler"
      continue
    }
    case "$handler" in
      daemon-reload) reconcile::sudo systemctl daemon-reload ;;
      *) reconcile::sudo systemctl restart "$handler" ;;
    esac
    reconcile::changed "handler $handler"
  done
  _reconcile_handlers=()
}

# --- zfs --------------------------------------------------------------------

reconcile::zpool_property() {
  local pool="$1" property="$2" value="$3" current
  current="$(reconcile::sudo zpool get -H -o value "$property" "$pool" 2>/dev/null)"
  if [[ "$current" == "$value" ]]; then
    reconcile::ok "zpool $pool $property"
    return 0
  fi
  reconcile::check && {
    reconcile::changed "zpool $pool $property=$value (was ${current:-?})"
    return 0
  }
  reconcile::sudo zpool set "$property=$value" "$pool"
  reconcile::changed "zpool $pool $property=$value"
}
