#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../ansible"

playbook="${1:-}"

if [[ -z "$playbook" ]]; then
  case "$(hostname -s)" in
    ML-*) playbook=work ;;
    pod042) playbook=pod042 ;;
    *) playbook=macos ;;
  esac
fi

if [[ ! -f "playbooks/$playbook.yml" ]]; then
  printf 'No such playbook: %s\n' "$playbook" >&2
  printf 'Available: %s\n' \
    "$(find playbooks -maxdepth 1 -name '*.yml' | sed 's|.*/||; s|\.yml$||' | sort | tr '\n' ' ')" >&2
  exit 1
fi

if [[ "$(uname)" == "Darwin" ]]; then
  control=inventory/control/macos.ini
else
  control=inventory/control/linux.ini
fi

declare -a inventory=()
case "$playbook" in
  truenas) inventory=(-i inventory/targets -i "$control") ;;
  pod042) inventory=(-i inventory/targets/pod042.yml) ;;
  *) inventory=(-i "$control") ;;
esac

exec ansible-playbook "${inventory[@]}" "playbooks/$playbook.yml" --list-tags
