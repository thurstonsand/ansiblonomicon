#!/usr/bin/env bash
set -euo pipefail

publish=true
if [[ "${1:-}" == "--dry-run" ]]; then
  publish=false
elif (( $# > 0 )); then
  echo "Usage: $0 [--dry-run]" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
render_dir="$(mktemp -d)"
checkout_dir="$(mktemp -d)"
trap 'rm -rf "$render_dir" "$checkout_dir"' EXIT

ANSIBLE_CONFIG="$repo_root/ansible/ansible.cfg" \
  uv run --directory "$repo_root" --no-sync ansible-playbook \
  -i localhost, \
  "$repo_root/ansible/playbooks/publish-amp-skills.yml" \
  -e "agent_harness_amp_skills_dir=$render_dir"

uv run --directory "$repo_root" --no-sync \
  "$repo_root/scripts/prepare_amp_skills.py" "$render_dir"

repository="$(amp skills repositories --json | jq -ce '.[] | select(.scope == "user")')"
clone_url="$(jq -r '.cloneURL' <<<"$repository")"

if [[ "$(jq -r '.exists' <<<"$repository")" == "true" ]]; then
  rm -rf "$checkout_dir"
  amp clone user-skills "$checkout_dir"
else
  git -C "$checkout_dir" init --initial-branch=main
  git -C "$checkout_dir" remote add origin "$clone_url"
  git -C "$checkout_dir" config credential.helper '!amp git-credential-helper'
fi

rsync -a --delete --exclude=.git "$render_dir/" "$checkout_dir/"
git -C "$checkout_dir" add --all

if git -C "$checkout_dir" diff --cached --quiet; then
  echo "Amp User Skills are already current."
  exit 0
fi

if [[ "$publish" == "false" ]]; then
  echo "Amp User Skills changes ready to publish:"
  git -C "$checkout_dir" diff --cached --stat
  exit 0
fi

git -C "$checkout_dir" config user.name "$(git -C "$repo_root" log -1 --format=%an)"
git -C "$checkout_dir" config user.email "$(git -C "$repo_root" log -1 --format=%ae)"
source_revision="$(git -C "$repo_root" rev-parse --short HEAD)"
git -C "$checkout_dir" commit -m "Update skills from ansiblonomicon $source_revision"
git -C "$checkout_dir" push --set-upstream origin main
