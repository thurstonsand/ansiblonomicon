#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="chezmoi/dot_config/amp/plugins"
WRITE_FLAG="--write"
MODE="write"

if [[ "${1:-}" == "--check" || "${1:-}" == "-c" ]]; then
  WRITE_FLAG=""
  MODE="check"
elif [[ "${1:-}" == "--format" || "${1:-}" == "-f" ]]; then
  WRITE_FLAG="--write"
  MODE="write"
fi

if [[ ! -f "$ROOT_DIR/package.json" ]]; then
  echo "No amp plugin package found under $ROOT_DIR"
  exit 0
fi

echo "==> biome $MODE $ROOT_DIR"
(
  cd "$ROOT_DIR"
  mapfile -t files < <(find . -type f \
    \( -name '*.ts' -o -name 'package.json' -o -name 'tsconfig.json' -o -name 'biome.json' \) \
    -not -path './node_modules/*' | sort)
  if [[ ${#files[@]} -gt 0 ]]; then
    npx biome check $WRITE_FLAG "${files[@]}"
  fi
  echo "==> tsc $ROOT_DIR"
  npx tsc --noEmit
  echo "==> test $ROOT_DIR"
  npm test
)
