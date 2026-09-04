#!/usr/bin/env bash
# The PLAY RECAP analog. Each unit task writes to the shared ledger; this reads
# it once the whole graph has finished, which is what `depends_post` is for.
set -uo pipefail

ledger="${RECONCILE_LEDGER:-/run/mise-reconcile.ledger}"
if [[ ! -r "$ledger" ]]; then
  echo "recap: no ledger at $ledger"
  exit 0
fi

printf '\n%-18s %8s %8s %8s\n' UNIT ok changed failed
awk -F'\t' '{ seen[$2] = 1; count[$2 "\t" $1]++ }
  END {
    for (unit in seen) {
      printf "%s\t%d\t%d\t%d\n", unit,
        count[unit "\tok"] + 0, count[unit "\tchanged"] + 0, count[unit "\tfailed"] + 0
    }
  }' "$ledger" | sort | awk -F'\t' '
    { printf "%-18s %8d %8d %8d\n", $1, $2, $3, $4; ok += $2; ch += $3; fail += $4 }
    END { printf "%-18s %8d %8d %8d\n", "TOTAL", ok + 0, ch + 0, fail + 0 }'

if grep -q '^changed' "$ledger"; then
  echo
  echo "changed resources:"
  awk -F'\t' '$1 == "changed" { printf "  [%s] %s\n", $2, $3 }' "$ledger"
fi
