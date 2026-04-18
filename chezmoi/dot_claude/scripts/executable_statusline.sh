#!/usr/bin/env bash
set -euo pipefail
trap 'echo "[statusline error]" >&2' ERR

# =============================================================================
# CONFIGURATION
# =============================================================================

BAR_LENGTH=20
COMPACTION_THRESHOLD=80 # raw context % where compaction fires; gauge maps this to 100%
CACHE_DIR="${HOME}/.cache/claude-statusline"

# =============================================================================
# COLORS
# =============================================================================

# Fixed 256-palette Gruvbox indices (16-231) because CC's statusline
# renderer doesn't theme-map ANSI 0-15.
CURRENT_THEME=$(cat ~/.terminal-bg 2>/dev/null || echo "dark")
RESET='\033[0m'

BG_GREEN='\033[48;5;143m'  # #98971a (neutral)
BG_YELLOW='\033[48;5;179m' # #d79921 (neutral)
BG_RED='\033[48;5;167m'    # #cc241d (neutral)

if [[ "$CURRENT_THEME" == "light" ]]; then
  BG_DIM='\033[48;5;187m'      # #d5c4a1
  FG_CONTRAST='\033[38;5;16m'  # fixed black
  SILVER='\033[38;5;241m'      # #626262 (bright — high contrast on light bg)
  STYLE_PALETTE=(
    '\033[38;5;126m' # #8f3f71 purple (faded)
    '\033[38;5;65m'  # #427b58 aqua (faded)
    '\033[38;5;136m' # #af8700 yellow (faded)
    '\033[38;5;100m' # #79740e green (faded)
    '\033[38;5;124m' # #9d0006 red (faded)
    '\033[38;5;130m' # #af3a03 orange (faded)
  )
else
  BG_DIM='\033[48;5;239m'       # #504945
  FG_CONTRAST='\033[38;5;255m'  # fixed white
  SILVER='\033[38;5;246m'       # #a89984 (light gray for dark bg)
  STYLE_PALETTE=(
    '\033[38;5;175m' # #d3869b light purple
    '\033[38;5;108m' # #8ec07c light aqua
    '\033[38;5;214m' # #fabd2f bright yellow
    '\033[38;5;142m' # #b8bb26 bright green
    '\033[38;5;203m' # #fb4934 bright red
    '\033[38;5;208m' # #fe8019 bright orange
  )
fi

# =============================================================================
# ARGS
# =============================================================================

SECTION_ORDER=()
if [[ $# -eq 0 ]]; then
  SECTION_ORDER=(gauge folder branch style)
else
  for arg in "$@"; do
    case "$arg" in
    --gauge) SECTION_ORDER+=(gauge) ;;
    --model) SECTION_ORDER+=(model) ;;
    --folder) SECTION_ORDER+=(folder) ;;
    --branch) SECTION_ORDER+=(branch) ;;
    --style) SECTION_ORDER+=(style) ;;
    esac
  done
fi

# =============================================================================
# CACHE
# =============================================================================

get_session_cache_file() {
  local sid="$1"
  [[ -n "$sid" ]] || return 0
  local safe_sid
  safe_sid=$(printf '%s' "$sid" | tr -cd 'a-zA-Z0-9_-')
  [[ -n "$safe_sid" ]] || return 0
  echo "${CACHE_DIR}/${safe_sid}.cache"
}

cleanup_stale_caches() {
  [[ -d "$CACHE_DIR" ]] || return 0
  find "$CACHE_DIR" -name "*.cache" -mtime +7 -delete 2>/dev/null || true
}

read_cache() {
  local cache_file="$1"
  [[ -n "$cache_file" && -f "$cache_file" ]] || return 1
  local cache_data
  cache_data=$(cat "$cache_file" 2>/dev/null) || return 1
  [[ -n "$cache_data" ]] || return 1
  mapfile -t _cache < <(awk -F'\t' '{for(i=1;i<=5;i++) print $i}' <<<"$cache_data")
  CACHED_USED_PCT="${_cache[0]}"
  CACHED_MODEL="${_cache[1]}"
  CACHED_DIR="${_cache[2]}"
  CACHED_BRANCH="${_cache[3]}"
  CACHED_STYLE="${_cache[4]}"
  [[ "$CACHED_USED_PCT" =~ ^[0-9]+$ ]]
}

write_cache() {
  local cache_file="$1"
  [[ -n "$cache_file" ]] || return 1
  mkdir -p "$CACHE_DIR" 2>/dev/null || return 1
  local tmp_file="${cache_file}.tmp.$$"
  printf '%s\t%s\t%s\t%s\t%s' "$2" "$3" "$4" "$5" "$6" >"$tmp_file" 2>/dev/null || {
    rm -f "$tmp_file"
    return 1
  }
  mv "$tmp_file" "$cache_file" 2>/dev/null || {
    rm -f "$tmp_file"
    return 1
  }
}

# =============================================================================
# RENDER
# =============================================================================

get_bg_color() {
  local used_pct=$1
  if [[ $used_pct -lt 50 ]]; then
    echo "$BG_GREEN"
  elif [[ $used_pct -lt 75 ]]; then
    echo "$BG_YELLOW"
  else
    echo "$BG_RED"
  fi
}

build_gauge() {
  local used_pct=$1

  local bg_fill
  bg_fill=$(get_bg_color "$used_pct")

  local label="${used_pct}%"
  local pad_label=" ${label} "
  local pad_len=${#pad_label}

  local filled=$((used_pct * BAR_LENGTH / 100))

  local label_start=$(((BAR_LENGTH - pad_len) / 2))
  [[ $label_start -lt 0 ]] && label_start=0

  local bar=""
  for ((i = 0; i < BAR_LENGTH; i++)); do
    if [[ $i -ge $label_start && $i -lt $((label_start + pad_len)) ]]; then
      local li=$((i - label_start))
      bar="${bar}${pad_label:$li:1}"
    else
      bar="${bar} "
    fi
  done

  local filled_part="${bar:0:$filled}"
  local empty_part="${bar:$filled}"

  local gauge=""
  [[ -n "$filled_part" ]] && gauge="${FG_CONTRAST}${bg_fill}${filled_part}${RESET}"
  [[ -n "$empty_part" ]] && gauge="${gauge}${FG_CONTRAST}${BG_DIM}${empty_part}${RESET}"

  printf '%b' "${gauge}"
}

render_section_model() {
  printf '%b' "${SILVER}$1${RESET}"
}

render_section_folder() {
  printf '%b' "${SILVER}📁 $1${RESET}"
}

render_section_branch() {
  local branch="$1"
  [[ -n "$branch" ]] || return
  printf '%b' "${SILVER}\ue725 $branch${RESET}"
}

hash_style_color() {
  local name="$1"
  local hash
  hash=$(printf '%s' "$name" | cksum | cut -d' ' -f1)
  echo $((hash % ${#STYLE_PALETTE[@]}))
}

render_section_style() {
  local style="$1"
  [[ -n "$style" ]] || return
  local idx
  idx=$(hash_style_color "$style")
  local color="${STYLE_PALETTE[$idx]}"
  printf '%b' "${color}◉ ${style}${RESET}"
}

output_line() {
  local used_pct=$1 model="$2" dir="$3" branch="$4" style="$5"
  local sections=()
  for section in "${SECTION_ORDER[@]}"; do
    case "$section" in
    gauge) sections+=("$(build_gauge "$used_pct")") ;;
    model) sections+=("$(render_section_model "$model")") ;;
    folder) sections+=("$(render_section_folder "$dir")") ;;
    branch) [[ -n "$branch" ]] && sections+=("$(render_section_branch "$branch")") ;;
    style) [[ -n "$style" ]] && sections+=("$(render_section_style "$style")") ;;
    esac
  done

  local out=""
  for ((i = 0; i < ${#sections[@]}; i++)); do
    [[ $i -gt 0 ]] && out+=" │ "
    out+="${sections[$i]}"
  done
  printf '%b\n' "$out"
}

# =============================================================================
# EXECUTE
# =============================================================================

cleanup_stale_caches

input=$(cat)

if ! command -v jq &>/dev/null; then
  echo "[statusline] jq not installed"
  exit 0
fi

mapfile -t _jq_fields < <(
  echo "$input" | jq -r '
        (.session_id // ""),
        (.model.display_name // "Unknown"),
        (.workspace.current_dir // "~"),
        (.output_style.name // ""),
        (.worktree.branch // ""),
        ((.context_window.used_percentage // "") | tostring)
    '
)
session_id="${_jq_fields[0]}"
model_display="${_jq_fields[1]}"
current_dir="${_jq_fields[2]}"
output_style="${_jq_fields[3]}"
worktree_branch="${_jq_fields[4]}"
USED_PCT="${_jq_fields[5]}"

for var in session_id model_display current_dir output_style worktree_branch; do
  printf -v "$var" '%s' "$(printf '%s' "${!var}" | tr -d '\000-\037\177')"
done

dir_name="${current_dir##*/}"

[[ -z "$dir_name" || "$dir_name" == "~" ]] && dir_name="${PWD##*/}"
[[ -z "$model_display" || "$model_display" == "Unknown" ]] && model_display="Claude"

git_branch="$worktree_branch"
if [[ -z "$git_branch" && -n "$current_dir" && "$current_dir" != "~" ]]; then
  git_branch=$(git -C "$current_dir" symbolic-ref --short HEAD 2>/dev/null | tr -d '\000-\037\177' || true)
fi

SESSION_CACHE_FILE=$(get_session_cache_file "$session_id")

if [[ ! "$USED_PCT" =~ ^[0-9]+$ ]] || [[ "$USED_PCT" == "0" ]]; then
  if [[ -n "$SESSION_CACHE_FILE" ]] && read_cache "$SESSION_CACHE_FILE"; then
    output_line "$CACHED_USED_PCT" "$CACHED_MODEL" "$CACHED_DIR" "$CACHED_BRANCH" "$CACHED_STYLE"
  else
    output_line 0 "$model_display" "$dir_name" "$git_branch" "$output_style"
  fi
  exit 0
fi

NORM_USED=$((USED_PCT * 100 / COMPACTION_THRESHOLD))
[[ $NORM_USED -gt 100 ]] && NORM_USED=100

output_line "$NORM_USED" "$model_display" "$dir_name" "$git_branch" "$output_style"

write_cache "$SESSION_CACHE_FILE" "$NORM_USED" "$model_display" "$dir_name" "$git_branch" "$output_style" || true
