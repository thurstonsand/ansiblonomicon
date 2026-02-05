#!/usr/bin/env bash
# Wrapper script that auto-detects control node platform and runs ansible-playbook
# with both target and control node inventories.
#
# Usage: ./run-playbook.sh <playbook> [ansible-playbook args...]
# Example: ./run-playbook.sh playbooks/truenas.yml --diff --tags homepage

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Auto-detect control node platform
if [[ "$(uname)" == "Darwin" ]]; then
    CONTROL_INV="inventory/control/macos.ini"
else
    CONTROL_INV="inventory/control/linux.ini"
fi

# First arg is the playbook, rest are passed through
PLAYBOOK="${1:?Usage: $0 <playbook> [args...]}"
shift

# Include both target hosts and control node localhost
exec ansible-playbook -i inventory/targets -i "$CONTROL_INV" "$PLAYBOOK" "$@"
