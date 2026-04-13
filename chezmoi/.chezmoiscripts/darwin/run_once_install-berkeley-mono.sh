#!/bin/bash
# Install Berkeley Mono Nerd Font from 1Password
# This runs once per machine (run_once prefix)

set -euo pipefail

FONT_DIR="$HOME/Library/Fonts"
OP_ACCOUNT_PREFIX="PQ7X5"

resolve_op_account() {
  op account list --format=json \
    | jq -re --arg prefix "$OP_ACCOUNT_PREFIX" '[.[] | select(.account_uuid | startswith($prefix))][0].account_uuid'
}

# Check if font files are already present
EXPECTED_FILES=(
  "BerkeleyMonoNerdFontMono-Regular.otf"
  "BerkeleyMonoNerdFontMono-Bold.otf"
  "BerkeleyMonoNerdFontMono-Oblique.otf"
  "BerkeleyMonoNerdFontMono-BoldOblique.otf"
)
MISSING=0
for f in "${EXPECTED_FILES[@]}"; do
  if [[ ! -f "$FONT_DIR/$f" ]]; then
    MISSING=1
    break
  fi
done

if [[ $MISSING -eq 0 ]]; then
  echo "BerkeleyMono Nerd Font Mono (all variants) already installed, skipping."
  exit 0
fi

# Verify 1Password item exists before attempting download
OP_ACCOUNT=$(resolve_op_account)
if ! op item get "Berkeley Mono Font" --vault Private --account "$OP_ACCOUNT" > /dev/null 2>&1; then
  echo "Warning: 1Password item 'Private/Berkeley Mono Font' not available — skipping font install."
  exit 0
fi

echo "Installing BerkeleyMono Nerd Font Mono from 1Password..."

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

op read "op://Private/Berkeley Mono Font/nerd-font" --account "$OP_ACCOUNT" --out-file "$TEMP_DIR/berkeley-mono.zip"

mkdir -p "$FONT_DIR"
unzip -q "$TEMP_DIR/berkeley-mono.zip" -d "$TEMP_DIR"
cp "$TEMP_DIR"/*.otf "$FONT_DIR/"

echo "BerkeleyMono Nerd Font Mono installed successfully."
