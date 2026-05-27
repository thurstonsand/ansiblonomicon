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

  if command -v mise >/dev/null 2>&1; then
    local mise_pi_bin=""
    mise_pi_bin="$(mise which pi 2>/dev/null || true)"
    if [[ -n "$mise_pi_bin" ]]; then
      pi_bin="$mise_pi_bin"
    fi
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
    mapfile -t PI_DEPS < <(PI_VERSION="$PI_VERSION" node <<'NODE'
const pkg = require("./package.json");
const names = [
  "@earendil-works/pi-agent-core",
  "@earendil-works/pi-ai",
  "@earendil-works/pi-coding-agent",
  "@earendil-works/pi-tui",
];
for (const name of names) {
  if (pkg.dependencies?.[name] || pkg.devDependencies?.[name] || pkg.peerDependencies?.[name]) {
    console.log(`${name}@${process.env.PI_VERSION}`);
  }
}
NODE
)
    if [[ ${#PI_DEPS[@]} -gt 0 ]]; then
      PI_VERSION="$PI_VERSION" npm install --save-dev "${PI_DEPS[@]}" @types/node@latest typescript@latest @biomejs/biome@latest
    fi
    npm update
  )
done

echo "Updated ${#PACKAGE_DIRS[@]} package(s) to pi ${PI_VERSION} and latest auxiliary deps."
