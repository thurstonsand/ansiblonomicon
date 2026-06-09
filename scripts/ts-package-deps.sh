#!/usr/bin/env bash
set -euo pipefail

PI_ROOT_DIR="chezmoi/private_dot_pi/agent/extensions"
AMP_ROOT_DIR="chezmoi/dot_config/amp/plugins"
SESSION_RECOVERY_DIR="chezmoi/dot_local/lib/session-recovery"

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

collect_package_dirs() {
  find "$PI_ROOT_DIR" "$AMP_ROOT_DIR" "$SESSION_RECOVERY_DIR" -name package.json -not -path '*/node_modules/*' -exec dirname {} \; | sort
}

package_has_dependency() {
  local name="$1"
  node - "$name" <<'NODE'
const pkg = require("./package.json");
const name = process.argv[2];
if (pkg.dependencies?.[name] || pkg.devDependencies?.[name] || pkg.peerDependencies?.[name]) {
  process.exit(0);
}
process.exit(1);
NODE
}

PI_PACKAGE_JSON="$(find_pi_package_json)"
PI_VERSION="$(node -p "require(process.argv[1]).version" "$PI_PACKAGE_JSON")"

mapfile -t PACKAGE_DIRS < <(collect_package_dirs)

# The Pi session-recovery extension depends on the shared library via a
# live-layout `file:` path that only resolves on the deployed machine (chezmoi's
# run_onchange installer links it there). `npm install` in the source checkout
# would fail, and it carries no registry deps to pin, so skip it. The shared
# library it points at (under dot_local/lib) is tracked normally.
FILTERED_DIRS=()
for dir in "${PACKAGE_DIRS[@]}"; do
  case "$dir" in
    */private_dot_pi/agent/extensions/session-recovery) continue ;;
  esac
  FILTERED_DIRS+=("$dir")
done
PACKAGE_DIRS=("${FILTERED_DIRS[@]}")

if [[ ${#PACKAGE_DIRS[@]} -eq 0 ]]; then
  echo "No TypeScript package.json files found under $PI_ROOT_DIR or $AMP_ROOT_DIR"
  exit 0
fi

UPDATED=0

for dir in "${PACKAGE_DIRS[@]}"; do
  echo "==> Updating deps in $dir"
  (
    cd "$dir"
    npm install

    mapfile -t HARNESS_DEPS < <(PI_VERSION="$PI_VERSION" node <<'NODE'
const pkg = require("./package.json");
const piNames = [
  "@earendil-works/pi-agent-core",
  "@earendil-works/pi-ai",
  "@earendil-works/pi-coding-agent",
  "@earendil-works/pi-tui",
];
for (const name of piNames) {
  if (pkg.dependencies?.[name] || pkg.devDependencies?.[name] || pkg.peerDependencies?.[name]) {
    console.log(`${name}@${process.env.PI_VERSION}`);
  }
}
if (pkg.dependencies?.["@ampcode/plugin"] || pkg.devDependencies?.["@ampcode/plugin"] || pkg.peerDependencies?.["@ampcode/plugin"]) {
  console.log("@ampcode/plugin@latest");
}
NODE
)

    AUX_DEPS=()
    for dep in @types/node typescript @biomejs/biome; do
      if package_has_dependency "$dep"; then
        AUX_DEPS+=("$dep@latest")
      fi
    done

    if [[ ${#HARNESS_DEPS[@]} -gt 0 || ${#AUX_DEPS[@]} -gt 0 ]]; then
      npm install --save-dev "${HARNESS_DEPS[@]}" "${AUX_DEPS[@]}"
    fi

    npm update
  )
  UPDATED=$((UPDATED + 1))
done

echo "Updated $UPDATED TypeScript package(s). Pi harness deps pinned to pi ${PI_VERSION}; Amp plugin deps updated to latest."
