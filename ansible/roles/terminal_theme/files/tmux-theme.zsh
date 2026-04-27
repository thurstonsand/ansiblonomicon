_apply_tmux_gruvbox() {
  local theme="${1:-dark}"
  tmux source-file ~/.config/tmux/gruvbox-"$theme".conf
}

_set_theme() {
  local mode="$1"
  ~/.local/bin/terminal-theme-switch.py "$mode"
  if [[ -n "$TMUX" ]]; then
    _apply_tmux_gruvbox "$mode"
  fi
}

bglight() { _set_theme light; }
bgdark() { _set_theme dark; }
