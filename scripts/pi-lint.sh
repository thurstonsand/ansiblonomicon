#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="chezmoi/private_dot_pi/agent/extensions"
WRITE_FLAG=""
MODE="check"

if [[ "${1:-}" == "--format" || "${1:-}" == "-f" ]]; then
  WRITE_FLAG="--write"
  MODE="write"
fi

mapfile -t PACKAGE_DIRS < <(find "$ROOT_DIR" -name package.json -not -path '*/node_modules/*' -exec dirname {} \; | sort)

# On the work machine the public npm registry is blocked, so packages with
# registry-only deps (e.g. parallel-web-tools' `parallel-web`) can't install and
# tsc can't resolve them. Skip those there; they still lint on personal machines.
WORK_HOSTNAME="ML-DFC6YK6VJQ"
if [[ "$(hostname -s 2>/dev/null || hostname)" == "$WORK_HOSTNAME" ]]; then
  FILTERED_DIRS=()
  for dir in "${PACKAGE_DIRS[@]}"; do
    case "$dir" in
      */parallel-web-tools) continue ;;
    esac
    FILTERED_DIRS+=("$dir")
  done
  PACKAGE_DIRS=("${FILTERED_DIRS[@]}")
fi

if [[ ${#PACKAGE_DIRS[@]} -eq 0 ]]; then
  echo "No pi extension packages found under $ROOT_DIR"
  exit 0
fi

for dir in "${PACKAGE_DIRS[@]}"; do
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
