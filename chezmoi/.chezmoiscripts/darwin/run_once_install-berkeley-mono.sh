#!/bin/bash
# Install Berkeley Mono Nerd Font from 1Password
# This runs once per machine (run_once prefix)

set -euo pipefail

FONT_DIR="$HOME/Library/Fonts"
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Check if all font variants are installed
VARIANTS=("Regular" "Bold" "Oblique" "Bold Oblique")
MISSING=0
for variant in "${VARIANTS[@]}"; do
  if ! fc-list | grep -q "BerkeleyMono Nerd Font Mono:style=$variant"; then
    MISSING=1
    break
  fi
done

if [[ $MISSING -eq 0 ]]; then
  echo "BerkeleyMono Nerd Font Mono (all variants) already installed, skipping."
  exit 0
fi

echo "Installing BerkeleyMono Nerd Font Mono from 1Password..."

# Download font zip from 1Password
op document get "Berkeley Mono Font" --vault "Private" --out-file "$TEMP_DIR/berkeley-mono.zip"

# Extract and install
unzip -q "$TEMP_DIR/berkeley-mono.zip" -d "$TEMP_DIR"
cp "$TEMP_DIR"/*.otf "$FONT_DIR/"

echo "BerkeleyMono Nerd Font Mono installed successfully."
