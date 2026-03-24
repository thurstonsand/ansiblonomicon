#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="chezmoi/private_dot_pi/agent/extensions"

find_pi_package_json() {
  local pi_bin=""
  pi_bin="$(command -v pi 2>/dev/null || true)"
  if [[ -z "$pi_bin" ]]; then
    echo "Could not find 'pi' on PATH." >&2
    return 1
  fi

  node - "$pi_bin" <<'NODE'
const fs = require("fs");
const path = require("path");
const piBin = process.argv[2];
const realBin = fs.realpathSync(piBin);
const packageJson = path.join(path.dirname(realBin), "..", "package.json");
if (!fs.existsSync(packageJson)) {
  console.error(`Could not locate package.json next to pi binary: ${packageJson}`);
  process.exit(1);
}
process.stdout.write(packageJson);
NODE
}

PI_PACKAGE_JSON="$(find_pi_package_json)"
PI_VERSION="$(node -p "require(process.argv[1]).version" "$PI_PACKAGE_JSON")"

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
