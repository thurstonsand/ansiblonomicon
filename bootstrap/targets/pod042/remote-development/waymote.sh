#!/usr/bin/env bash
# Upstream release binaries are built for the CI runner's CPU and die with SIGILL on
# pod042's i5-12600K, which lacks AVX-512, so build the version Amp expects for x86-64-v3.
set -euo pipefail

version=0.1.5
bin="$HOME/.local/bin"

if [ "$("$bin/waymote-streamd" --version 2>/dev/null || true)" = "waymote-streamd $version (protocol 2)" ] &&
    [ "$("$bin/waymote-gateway" -version 2>/dev/null || true)" = "waymote-gateway $version (protocol 2)" ]; then
    exit 0
fi

source=$(mktemp -d)
trap 'rm -rf "$source"' EXIT
git clone --quiet --depth 1 --branch "v$version" https://github.com/rockorager/waymote "$source"
(
    cd "$source"
    mise exec zig@0.16.0 go@latest -- zig build install \
        -Doptimize=ReleaseSafe -Dversion="$version" -Dcpu=x86_64_v3 --prefix "$source/out"
)
install -m 0755 "$source/out/bin/waymote-streamd" "$source/out/bin/waymote-gateway" "$bin/"
"$bin/waymote-streamd" --version
