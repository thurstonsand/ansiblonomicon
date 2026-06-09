#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 [--hash] <root> [root...]" >&2
}

hash_mode=false
if [ "${1:-}" = "--hash" ]; then
  hash_mode=true
  shift
fi

if [ "$#" -eq 0 ]; then
  usage
  exit 2
fi

find_package_jsons() {
  for root in "$@"; do
    [ -d "$root" ] || continue
    find "$root" \
      \( \
        -path '*/node_modules' -o \
        -path '*/.git' -o \
        -path '*/dist' -o \
        -path '*/build' -o \
        -path '*/coverage' -o \
        -path '*/.cache' -o \
        -path '*/.turbo' \
      \) -prune -o \
      -name package.json -type f -print
  done | sort
}

if [ "$hash_mode" = false ]; then
  find_package_jsons "$@"
  exit 0
fi

{
  sha256sum "$0"
  find_package_jsons "$@" | while IFS= read -r package_json; do
    package_dir=$(dirname "$package_json")
    sha256sum "$package_json"
    if [ -f "$package_dir/package-lock.json" ]; then
      sha256sum "$package_dir/package-lock.json"
    fi
  done
} | sha256sum | awk '{print $1}'
