_apply_tmux_gruvbox() {
  local theme="${1:-dark}"
  if [[ "$theme" == "light" ]]; then
    tmux set-option -g status-style 'bg=#ebdbb2,fg=#7c6f64,nobold,noitalics,nounderscore'
    tmux set-option -g status-left '#[bg=#7c6f64,fg=#f9f5d7,bold,noitalics,nounderscore] #{s|^ide-(.+)-[a-f0-9]+$|\1|:session_name} #[bg=#d5c4a1,fg=#7c6f64,nobold,noitalics,nounderscore]'
    tmux set-option -g window-status-separator '#[bg=#d5c4a1,fg=#d5c4a1]  '
    tmux set-option -g window-status-format '#[bg=#d5c4a1,fg=#928374,nobold,noitalics,nounderscore] #W#{?window_end_flag, #[bg=#ebdbb2,fg=#d5c4a1,nobold,noitalics,nounderscore],}'
    tmux set-option -g window-status-current-format '#[bg=#d5c4a1,fg=#b57614,nobold,noitalics,nounderscore] #W#{?window_end_flag, #[bg=#ebdbb2,fg=#d5c4a1,nobold,noitalics,nounderscore],}'
    tmux set-option -g status-right '#[bg=#ebdbb2,fg=#7c6f64,nobold,noitalics,nounderscore]#[bg=#7c6f64,fg=#f9f5d7,bold,noitalics,nounderscore] #h '
  else
    tmux source-file ~/.config/tmux/tmux.conf
  fi
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
