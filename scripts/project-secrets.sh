_fnox_exports="$("$(dirname "${BASH_SOURCE[0]}")/fnox-host" export)" || exit "$?"
eval "$_fnox_exports"
unset _fnox_exports
