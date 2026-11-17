#!/usr/bin/env bash
set -euo pipefail

ROOT_DIRS=(
  "bootstrap/capabilities/agent-harness/configuration/assets/pi/extensions"
  "bootstrap/capabilities/agent-harness/configuration/assets/pi/permissions"
)
WRITE_FLAG=""
MODE="check"

if [[ "${1:-}" == "--format" || "${1:-}" == "-f" ]]; then
  WRITE_FLAG="--write"
  MODE="write"
fi

# The work mirror can't serve these packages' locked dependencies, so bootstrap
# never installs them there and biome/tsc have nothing to run with. They still
# lint on personal machines.
if [[ "$(hostname -s 2>/dev/null || hostname)" == "ML-DFC6YK6VJQ" ]]; then
  echo "Skipping pi package lint on the work machine"
  exit 0
fi

mapfile -t PACKAGE_DIRS < <(find "${ROOT_DIRS[@]}" -name package.json -not -path '*/node_modules/*' -exec dirname {} \; | sort)

if [[ ${#PACKAGE_DIRS[@]} -eq 0 ]]; then
  echo "No pi extension packages found under ${ROOT_DIRS[*]}"
  exit 0
fi

for dir in "${PACKAGE_DIRS[@]}"; do
  echo "==> lockfile $MODE $dir"
  (
    cd "$dir"
    # `npm ci` accepts a lockfile the registry can no longer resolve; re-resolving it catches that.
    committed=$(mktemp)
    trap 'rm -f "$committed"' EXIT
    cp package-lock.json "$committed"
    npm install --package-lock-only --ignore-scripts --no-audit --no-fund --loglevel=error
    if [[ "$MODE" == "check" ]] && ! cmp -s "$committed" package-lock.json; then
      diff -u "$committed" package-lock.json | head -40 || true
      cp "$committed" package-lock.json
      echo "$dir/package-lock.json no longer resolves as committed; run mise run pi:fix" >&2
      exit 1
    fi
  )
  echo "==> biome $MODE $dir"
  (
    cd "$dir"
    mapfile -t files < <(find . -type f -not -path '*/node_modules/*' \( -name '*.ts' -o -name 'package.json' -o -name 'tsconfig.json' -o -name 'biome.json' \) | sort)
    if [[ ${#files[@]} -gt 0 ]]; then
      npx biome check $WRITE_FLAG "${files[@]}"
    fi
    echo "==> tsc $dir"
    npx tsc --noEmit
  )
done
