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

if [[ ${#PACKAGE_DIRS[@]} -eq 0 ]]; then
  echo "No pi extension packages found under $ROOT_DIR"
  exit 0
fi

for dir in "${PACKAGE_DIRS[@]}"; do
  echo "==> biome $MODE $dir"
  (
    cd "$dir"
    mapfile -t files < <(find . -maxdepth 1 -type f \( -name '*.ts' -o -name 'package.json' -o -name 'tsconfig.json' -o -name 'biome.json' \) | sort)
    if [[ ${#files[@]} -gt 0 ]]; then
      npx biome check $WRITE_FLAG --config-path . "${files[@]}"
    fi
    echo "==> tsc $dir"
    npx tsc --noEmit
  )
done
