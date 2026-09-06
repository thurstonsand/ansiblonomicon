#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../ansible"

playbook="${1:-}"

if [[ -z "$playbook" ]]; then
  case "$(hostname -s)" in
    ML-DFC6YK6VJQ) playbook=work ;;
    pod042) playbook=pod042 ;;
    Thurstons-MacBook-Pro) playbook=macos ;;
    *) echo "Unregistered reconciliation host" >&2; exit 1 ;;
  esac
fi

if [[ "$playbook" == pod042 ]]; then
  exec python3 -B -c 'import sys; sys.path.insert(0, "../scripts"); from pod042_reconcile import CAPABILITIES; print("\n".join(CAPABILITIES))'
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

exec ansible-playbook -i "$control" "playbooks/$playbook.yml" --list-tags
