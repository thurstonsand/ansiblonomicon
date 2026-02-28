_apply_tmux_gruvbox() {
  local theme="${1:-dark}"
  tmux source-file ~/.config/tmux/gruvbox-"$theme".conf
}

bglight() {
  echo "light" > ~/.terminal-bg
  export TERMINAL_BG=light
  if [[ -n "$TMUX" ]]; then
    tmux set-environment TERMINAL_BG light
    _apply_tmux_gruvbox light
  fi
}

bgdark() {
  echo "dark" > ~/.terminal-bg
  export TERMINAL_BG=dark
  if [[ -n "$TMUX" ]]; then
    tmux set-environment TERMINAL_BG dark
    _apply_tmux_gruvbox dark
  fi
}
