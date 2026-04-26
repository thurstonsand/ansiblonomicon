#!/usr/bin/env bash
set -euo pipefail

LOCKFILE_RE='(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|uv\.lock)$'

declare -a diff_targets=()
declare -a ignored_targets=()

if [[ $# -gt 0 ]]; then
  diff_targets=("$@")
else
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    target="${line:3}"
    [[ -z "$target" ]] && continue

    if [[ "$target" =~ $LOCKFILE_RE ]]; then
      ignored_targets+=("$target")
    else
      diff_targets+=("$target")
    fi
  done < <(chezmoi status --path-style absolute)
fi

if [[ ${#diff_targets[@]} -eq 0 ]]; then
  if [[ ${#ignored_targets[@]} -gt 0 ]]; then
    printf 'No non-lockfile chezmoi changes to diff. Ignored %d lockfile change(s).\n' "${#ignored_targets[@]}" >&2
  else
    echo 'No chezmoi changes to diff.' >&2
  fi
  exit 0
fi

if [[ ${#ignored_targets[@]} -gt 0 ]]; then
  printf 'Ignoring %d lockfile change(s) in chezmoi diff.\n' "${#ignored_targets[@]}" >&2
fi

if [[ -t 1 ]] && command -v delta >/dev/null 2>&1; then
  # Work around a chezmoi/delta pager regression: `chezmoi diff <targets>` no longer
  # gives delta a usable interactive pager path. Revisit this later; if upstream
  # behavior is fixed, this should collapse back to `chezmoi diff "${diff_targets[@]}"`.
  chezmoi diff --no-pager "${diff_targets[@]}" | delta --paging=always --pager "less -R"
else
  exec chezmoi diff --no-pager "${diff_targets[@]}"
fi
