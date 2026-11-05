#!/usr/bin/env bash
set -euo pipefail

publish=true
if [[ "${1:-}" == "--dry-run" && $# == 1 ]]; then
  publish=false
elif (( $# > 0 )); then
  echo "Usage: $0 [--dry-run]" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$repo_root/bootstrap/capabilities/agent-harness/amp-plugins"
checkout_dir="$(mktemp -d)"
trap 'rm -rf "$checkout_dir"' EXIT

repository="$(amp plugins repositories --json | jq -ce '.[] | select(.scope == "user" and .viewerCanWrite)')"
clone_url="$(jq -r '.cloneURL' <<<"$repository")"

if [[ "$(jq -r '.exists' <<<"$repository")" == "true" ]]; then
  rm -rf "$checkout_dir"
  amp clone user-plugins "$checkout_dir"
else
  git -C "$checkout_dir" init --initial-branch=main
  git -C "$checkout_dir" remote add origin "$clone_url"
  git -C "$checkout_dir" config credential.helper '!amp git-credential-helper'
fi

# Each source owns one root path; other hosted plugins are not ours to delete.
for source in "$source_dir"/*; do
  rsync -a --delete "$source" "$checkout_dir/"
  git -C "$checkout_dir" add -- "$(basename "$source")"
done

if git -C "$checkout_dir" diff --cached --quiet; then
  echo "Amp User Plugins are already current."
  exit 0
fi

if [[ "$publish" == "false" ]]; then
  echo "Amp User Plugins changes ready to publish:"
  git -C "$checkout_dir" diff --cached --stat
  exit 0
fi

git -C "$checkout_dir" config user.name "$(git -C "$repo_root" log -1 --format=%an)"
git -C "$checkout_dir" config user.email "$(git -C "$repo_root" log -1 --format=%ae)"
source_revision="$(git -C "$repo_root" rev-parse --short HEAD)"
git -C "$checkout_dir" commit -m "Update plugins from ansiblonomicon $source_revision"
git -C "$checkout_dir" push --set-upstream origin main
