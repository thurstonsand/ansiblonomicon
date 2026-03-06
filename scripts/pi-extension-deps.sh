#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="chezmoi/private_dot_pi/agent/extensions"
PI_VERSION="$(node -p "require('/home/thurstonsand/.npm-global/lib/node_modules/@mariozechner/pi-coding-agent/package.json').version")"

mapfile -t PACKAGE_DIRS < <(find "$ROOT_DIR" -name package.json -not -path '*/node_modules/*' -exec dirname {} \; | sort)

if [[ ${#PACKAGE_DIRS[@]} -eq 0 ]]; then
  echo "No pi extension packages found under $ROOT_DIR"
  exit 0
fi

for dir in "${PACKAGE_DIRS[@]}"; do
  echo "==> Updating deps in $dir"
  (
    cd "$dir"
    npm install
    if node -e 'const pkg=require("./package.json"); process.exit((pkg.dependencies?.["@mariozechner/pi-coding-agent"] || pkg.devDependencies?.["@mariozechner/pi-coding-agent"]) ? 0 : 1)'; then
      npm install --save-dev "@mariozechner/pi-coding-agent@${PI_VERSION}" @types/node@latest typescript@latest @biomejs/biome@latest
    fi
    npm update
  )
done

echo "Updated ${#PACKAGE_DIRS[@]} package(s) to pi ${PI_VERSION} and latest auxiliary deps."
