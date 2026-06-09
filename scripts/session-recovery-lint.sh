#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="chezmoi/dot_local/lib/session-recovery"
CLAUDE_CONSUMER_DIR="chezmoi/dot_claude/scripts/session-recovery"
WRITE_FLAG=""
MODE="check"

if [[ "${1:-}" == "--format" || "${1:-}" == "-f" ]]; then
  WRITE_FLAG="--write"
  MODE="write"
fi

# The shared lib carries the biome/tsc toolchain; consumers borrow it so they
# need no devDeps of their own (keeps the work-network install registry-free).
TOOLCHAIN_BIN="$(cd "$ROOT_DIR/node_modules/.bin" && pwd)"

lint_package() {
  local dir="$1"
  echo "==> biome $MODE $dir"
  (
    cd "$dir"
    mapfile -t files < <(find . -type f \
      \( -name '*.ts' -o -name 'package.json' -o -name 'tsconfig.json' -o -name 'biome.json' \) \
      -not -path './node_modules/*' | sort)
    if [[ ${#files[@]} -gt 0 ]]; then
      "$TOOLCHAIN_BIN/biome" check $WRITE_FLAG "${files[@]}"
    fi
    echo "==> tsc $dir"
    "$TOOLCHAIN_BIN/tsc" --noEmit
  )
}

if [[ ! -f "$ROOT_DIR/package.json" ]]; then
  echo "No session-recovery package found under $ROOT_DIR"
  exit 0
fi

lint_package "$ROOT_DIR"

if [[ -f "$CLAUDE_CONSUMER_DIR/package.json" ]]; then
  lint_package "$CLAUDE_CONSUMER_DIR"
fi
