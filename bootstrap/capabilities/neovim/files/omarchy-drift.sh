#!/bin/sh
# Omarchy seeds ~/.config/nvim once and later edits it through migrations,
# so neither its package updates nor its in-place edits reach this repo on
# their own. Exit 1 lists what needs a human decision.
set -eu

package=/usr/share/omarchy-nvim/config
files=$(cd "$(dirname "$0")" && pwd -P)
config="$HOME/.config/nvim"
baseline="$files/omarchy-seed.sha256"

package_files=$(cd "$package" && find . -type f | sed 's|^\./||' | sort)
shadowed=$(for path in $package_files; do
  [ ! -e "$files/nvim/$path" ] || echo "$path"
done)

if [ "${1:-}" = --update ]; then
  (cd "$package" && sha256sum $shadowed) > "$baseline"
  echo "Recorded $(wc -l < "$baseline") shadowed Omarchy files in $baseline"
  exit 0
fi

findings=0
report() {
  echo "$1"
  findings=1
}

while read -r recorded path; do
  [ -e "$package/$path" ] && current=$(sha256sum < "$package/$path") || current=missing
  [ "${current%% *}" = "$recorded" ] ||
    report "Omarchy changed shadowed $path: diff $package/$path $files/nvim/$path, then --update"
done < "$baseline"

for path in $package_files; do
  case "$path" in lazy-lock.json) continue ;; esac
  echo "$shadowed" | grep -qxF "$path" && continue
  cmp -s "$package/$path" "$config/$path" || report "Omarchy's seed of $path is stale or missing: cp $package/$path $config/$path"
done

rendered=$(sed -n 's|^"~/.config/nvim/\(lua/[^"]*\)".*mode = "template".*|\1|p' "$files"/../mise*.toml)
for path in "$config"/lua/config/*.lua "$config"/lua/plugins/*.lua; do
  [ -L "$path" ] && continue
  relative=${path#"$config"/}
  [ -e "$package/$relative" ] && continue
  echo "$rendered" | grep -qxF "$relative" && continue
  report "Unexpected $relative: neither the repo nor the Omarchy package declares it"
done

exit "$findings"
