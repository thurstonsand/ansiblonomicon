_fnox_arguments=()
if [[ -n "${AMP_ORB:-}" ]]; then
  _fnox_arguments+=(--orb)
fi
_fnox_exports="$("$(dirname "${BASH_SOURCE[0]}")/fnox-host" "${_fnox_arguments[@]}" export)" || exit "$?"
eval "$_fnox_exports"
unset _fnox_arguments _fnox_exports
