#!/usr/bin/env bash
# Saves each executor/<slug>/ to the hosted Executor app with that slug and deploys that commit.
# Needs EXECUTOR_ACCESS_TOKEN, an Executor personal access token scoped to EXECUTOR_ORGANIZATION.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export EXECUTOR_HOST=https://api.executor.sh
: "${EXECUTOR_ACCESS_TOKEN:?}" "${EXECUTOR_ORGANIZATION:?}"

executor() {
  npx --yes "executor@${EXECUTOR_CLI_VERSION:?}" apps "$@" --organization "$EXECUTOR_ORGANIZATION"
}

apps="$(executor list)"
for dir in "$repo_root"/executor/*/; do
  slug="$(basename "$dir")"
  app="$(jq -er --arg slug "$slug" '.[] | select(.slug == $slug) | .id' <<<"$apps")"
  expected="$(executor source --app "$app" | jq -er '.revision.commit')"
  commit="$(executor commit --app "$app" --files "$dir" --expected "$expected" \
    --message "Deploy executor/$slug from ansiblonomicon ${GITHUB_SHA:-local}" | jq -er '.revision.commit')"
  deployed="$(executor deploy --app "$app" --commit "$commit" | jq -er '.version.sourceCommit')"
  if [[ "$deployed" != "$commit" ]]; then
    echo "$slug: deployed $deployed, expected $commit" >&2
    exit 1
  fi
  echo "$slug: deployed $commit"
done
