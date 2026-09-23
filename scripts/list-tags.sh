#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"

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
  exec python3 -B -c 'import sys; sys.path.insert(0, sys.argv[1]); from pod042_reconcile import CAPABILITIES; print("\n".join((*CAPABILITIES, "tmux")))' "$repo_root/scripts"
fi

case "$playbook" in
  macos) printf 'Native mise tags: sysconfig dock finder nsglobaldomain menubar desktop-services permissions hostname agent-harness agent-config berkeley-mono claude-code desktop-tools docker-context editor-config homebrew language-tools mac-apps mas mise opencode sessions shp uvc-util git-client jj-client ssh-client neovim nvim-deps shell terminal-theme terminal-tools tmux user-tools retirements\n'; exit 0 ;;
  work) printf 'Native mise tags: sysconfig dock finder nsglobaldomain menubar desktop-services permissions berkeley-mono desktop-tools editor-config homebrew language-tools mac-apps mas mise pi sessions uvc-util git-client jj-client neovim nvim-deps python-index shell terminal-theme terminal-tools tmux user-tools\n' ;;
  *) printf 'Unknown host: %s (expected macos, pod042, or work)\n' "$playbook" >&2; exit 1 ;;
esac
export ANSIBLE_CONFIG="$repo_root/ansible/ansible.cfg"
exec uv run --directory "$repo_root" --group work ansible-playbook \
  -i "$repo_root/ansible/inventory/control/macos.ini" \
  "$repo_root/ansible/playbooks/work.yml" --list-tags
