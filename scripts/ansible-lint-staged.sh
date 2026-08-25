#!/usr/bin/env bash
# Lint the staged Ansible files hk hands us, scoped to whole roles.
#
# ansible-lint only runs `ansible-playbook --syntax-check` on lintables of kind
# playbook, role, or pattern. A bare task file is kind `tasks` and gets no
# syntax check at all, so a staged task referencing a module that does not exist
# would pass. Collapsing anything under roles/<name>/ to roles/<name> costs about
# 0.3s and restores that coverage.
#
# Set ANSIBLE_LINT_STAGED_DRY_RUN=1 to print the normalized lintables instead of
# linting. That is the seam `hk test` uses: a step test can override env but not
# argv, and running the real linter per table row would cost 1.4s each.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# ansible-lint reads ansible/.ansible-lint and resolves collections relative to
# ansible/, so paths arrive repo-relative and leave ansible-relative.
lintables=()
for path in "$@"; do
  case "$path" in
    ansible/*) lintable=${path#ansible/} ;;
    *)
      printf 'ansible-lint-staged: %s is not under ansible/\n' "$path" >&2
      exit 2
      ;;
  esac

  case "$lintable" in
    roles/*/*)
      role=${lintable#roles/}
      lintable="roles/${role%%/*}"
      ;;
  esac

  for seen in ${lintables[@]+"${lintables[@]}"}; do
    if [[ "$seen" == "$lintable" ]]; then
      continue 2
    fi
  done
  lintables+=("$lintable")
done

if [[ ${#lintables[@]} -eq 0 ]]; then
  exit 0
fi

if [[ -n "${ANSIBLE_LINT_STAGED_DRY_RUN:-}" ]]; then
  printf '%s\n' "${lintables[@]}"
  exit 0
fi

cd "$repo_root/ansible"
# --offline skips the `ansible-galaxy collection install` every invocation would
# otherwise run (1.83s -> 1.36s per role). The full `ansible:lint` task stays
# online; that is where a newly added collection requirement surfaces.
exec ansible-lint --offline "${lintables[@]}"
