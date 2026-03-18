# Zellij → tmux Migration

## Problem Statement

The current Zellij-based terminal multiplexer setup on clawdbot (Debian VM accessed via SSH from macOS/Ghostty) has three blocking issues:

1. **OSC 52 clipboard broken**: Amp CLI's pty layer captures output, preventing raw escape sequences from reaching Zellij. Copy from within Amp doesn't reach the macOS clipboard.
2. **Link clicks handled server-side**: Zellij intercepts OSC 8 hyperlinks and runs `xdg-open` on the VM, which fails (no browser). Links should pass through to Ghostty for local opening.
3. **Session resurrection jank**: Zellij's `edit` and `command` panes show "Waiting to run" on session restore, requiring manual Enter presses.

A reverse-tunnel + socat shim approach was considered and rejected as too much infrastructure for basic functionality.

## Goals

1. Replace Zellij with tmux for the clawdbot SSH workflow
2. Working clipboard (OSC 52) through Amp CLI inside tmux
3. Working hyperlinks (OSC 8) that open in Ghostty/macOS
4. Equivalent session management via `ideoc()` shell function
5. Alt-key bindings for prefix-free pane/window navigation
6. Light/dark theme detection that works with the existing macOS scheduled switching
7. Persistent floating scratch session
8. Shared tmux config that works on both macOS and clawdbot (chezmoi-managed)

## Non-Goals

- Session persistence plugins (tmux-resurrect/continuum) — the layout is simple enough to script
- Explicit tmux theme engine — Ghostty provides terminal colors; tmux uses `default` to inherit
- tmux-yank — OSC 52 via `set-clipboard on` handles both platforms natively
- tmuxinator/tmuxp or similar session managers — `ideoc()` shell function is sufficient

## Design

> **Implementation note (2026-03-18):** the tmux migration itself still stands, but the theme-manager pieces described below are now owned by the Ansible `terminal_theme` role rather than chezmoi runtime scripts. Local macOS split navigation also moved to the Ghostty-native helper flow documented in `docs/designs/07-ghostty-btt-navigator.md`.

### tmux.conf

Chezmoi-managed at `chezmoi/dot_config/tmux/tmux.conf.tmpl`. Platform-specific sections use chezmoi conditionals where needed.

#### Core Settings

```tmux
# Terminal compatibility
set -g default-terminal "tmux-256color"
set -g allow-passthrough all
set -ga terminal-features ",*:hyperlinks:RGB"
set -s set-clipboard on
set -s extended-keys always
set -g extended-keys-format csi-u
set -as terminal-features 'xterm*:extkeys'
set -s escape-time 0
set -g focus-events on
set -g set-titles on
set -g set-titles-string "#{s|^ide-(.+)-[a-f0-9]+$|\\1|:session_name}:#{window_name}"

# Behavior
unbind C-b
set -g prefix M-a
bind M-a send-prefix
set -g mouse on
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on
set -g history-limit 50000
set -g display-time 4000
setw -g aggressive-resize on
set -g mode-keys vi
set -g status-keys emacs
```

#### Theme: Ghostty-Driven Gruvbox Sync

Ghostty still drives light/dark mode, but tmux now loads explicit gruvbox config files and updates shared state through a helper script. That keeps tmux, delta, nvim, Claude, and Codex aligned when the terminal theme changes.

```tmux
set -g status-position bottom
set -g pane-border-status top
set -g pane-border-format " #{pane_index}: #{pane_current_command} "

if-shell "[ \"$(cat ~/.terminal-bg 2>/dev/null)\" = light ]" \
  "source-file ~/.config/tmux/gruvbox-light.conf" \
  "source-file ~/.config/tmux/gruvbox-dark.conf"
set-hook -g client-dark-theme "run-shell '~/.local/bin/terminal-theme-switch.py dark'; set-environment -g TERMINAL_BG dark; source-file ~/.config/tmux/gruvbox-dark.conf"
set-hook -g client-light-theme "run-shell '~/.local/bin/terminal-theme-switch.py light'; set-environment -g TERMINAL_BG light; source-file ~/.config/tmux/gruvbox-light.conf"
```

#### Key Bindings

Daily navigation stays prefix-free. `C-b` is removed, `M-a` becomes the tmux prefix for commands that still need one, and the root-table shortcuts stay focused on window switching, zoom, scratch access, and copy mode.

```tmux
# Window switching
bind -n M-1 select-window -t :=1
bind -n M-2 select-window -t :=2
bind -n M-3 select-window -t :=3
bind -n M-4 select-window -t :=4
bind -n M-5 select-window -t :=5

# Zoom toggle
bind -n M-z resize-pane -Z

# Floating scratch session
bind -n M-s if-shell -F '#{==:#{session_name},scratch}' {
    detach-client
} {
    if-shell -F '#{==:#{pane_current_command},nvim}' {
        send-keys C-_
    } {
        display-popup -w 80% -h 80% -E "tmux new -As scratch"
    }
}

# Copy mode
bind -n M-[ copy-mode
```

#### Split Navigation

Remote tmux sessions still use tmux-native pane movement, but local macOS navigation has moved away from `vim-tmux-navigator` and into the Ghostty-native helper flow described in `docs/designs/07-ghostty-btt-navigator.md`.

That means this design doc is now only current for the tmux side of the migration. The staged Neovim config disables `christoomey/vim-tmux-navigator` locally and routes `Ctrl-h/j/k/l` through `ghostty-nav` instead.

### Session Management: `ideoc()` Function

Replaces the current Zellij-based `ideoc()` in `dot_zshrc.tmpl`. The current implementation creates a four-window workspace: repo/editor, repo agent, home, and home agent.

```zsh
ideoc() {
  local session="openclaw"

  if [[ -n "$TMUX" ]]; then
    if [[ "$(tmux display-message -p '#{session_name}')" == "$session" ]]; then
      echo "Already in session '$session'"
    else
      echo "Already inside tmux session '$(tmux display-message -p '#{session_name}')'. Detach first."
    fi
    return 1
  fi

  if [[ "$1" == "--recreate" ]]; then
    tmux kill-session -t "$session" 2>/dev/null
  fi

  if tmux has-session -t "$session" 2>/dev/null; then
    tmux attach -t "$session"
  else
    local ansi_hash
    ansi_hash=$(printf '%s' "$HOME/code/ansiblonomicon" | shasum | cut -c1-8)
    local home_hash
    home_hash=$(printf '%s' "$HOME" | shasum | cut -c1-8)

    tmux new-session -d -s "$session" -n ansiblonomicon -c ~/code/ansiblonomicon
    tmux new-window -t "$session" -n ansi_agent -c ~/code/ansiblonomicon
    tmux set-option -w -t "$session":ansi_agent @cwd_hash "$ansi_hash"
    tmux new-window -t "$session" -n home -c ~
    tmux new-window -t "$session" -n home_agent -c ~
    tmux set-option -w -t "$session":home_agent @cwd_hash "$home_hash"
    tmux select-window -t "$session":ansiblonomicon
    (sleep 1.0 && \
      pane_cmd=$(tmux list-panes -t "$session":ansiblonomicon -F '#{pane_current_command}' 2>/dev/null) && \
      [[ "$pane_cmd" == "zsh" || "$pane_cmd" == "bash" ]] && \
      tmux send-keys -t "$session":ansiblonomicon "nvim ." Enter
    ) &!
    (sleep 5.0 && \
      pane_cmd=$(tmux list-panes -t "$session":home -F '#{pane_current_command}' 2>/dev/null) && \
      [[ "$pane_cmd" == "zsh" || "$pane_cmd" == "bash" ]] && \
      tmux send-keys -t "$session":home "nvim ." Enter
    ) &!
    tmux attach -t "$session"
  fi
}
```

The macOS `ide()` function gets a similar rewrite, replacing Zellij with tmux. The session naming uses the same `ide-${dir_name}-${dir_hash}` pattern.

### SSH Auto-Attach

No change to the trigger logic — still clawdbot-only, still checks for SSH + interactive + not-already-in-multiplexer:

```zsh
{{- if eq .chezmoi.hostname "clawdbot" }}
if [[ -n "$SSH_CONNECTION" && -z "$TMUX" && $- == *i* ]]; then
  ideoc
fi
{{- end }}
```

Changes from current: `$ZELLIJ` check becomes `$TMUX` check.

### Terminal Background Detection

#### What Changes

| Component                      | Before (Zellij)           | After (tmux)                                                                                 |
| ------------------------------ | ------------------------- | -------------------------------------------------------------------------------------------- |
| `_detect_terminal_bg()`        | No change                 | **Removed from zsh startup** — Ansible now seeds `~/.terminal-bg`, shells just read it      |
| `_maybe_refresh_terminal_bg()` | Runs in precmd every 300s | **Removed** — OSC 11 can't round-trip inside tmux                                            |
| Theme helper                   | None                      | `terminal-theme-switch.py` updates `~/.terminal-bg`, Claude theme state, and Codex TUI theme |
| Source of truth                | `~/.terminal-bg` file     | `dark-notify` LaunchAgent → `terminal-theme-switch.py` → `~/.terminal-bg` and tool configs  |
| nvim file watcher              | Watches `~/.terminal-bg`  | **Kept unchanged** — reacts to helper-driven writes                                          |
| nvim FocusGained               | Not used                  | Not needed — file watcher is more responsive                                                 |

#### `bglight` / `bgdark` Functions

Manual override for mid-session theme changes now goes through a single helper so the side effects stay centralized:

```zsh
_set_theme() {
  local mode="$1"
  ~/.local/bin/terminal-theme-switch.py "$mode"
  export TERMINAL_BG="$mode"
  if [[ -n "$TMUX" ]]; then
    tmux set-environment TERMINAL_BG "$mode"
    tmux source-file ~/.config/tmux/gruvbox-"$mode".conf
  fi
}

bglight() { _set_theme light; }
bgdark() { _set_theme dark; }
```

#### Detection Flow

```
macOS theme changes → dark-notify LaunchAgent fires →
  ~/.local/bin/terminal-theme-watch reads light|dark →
  ~/.local/bin/terminal-theme-switch.py updates ~/.terminal-bg, ~/.claude.json, and ~/.codex/config.toml →
  new shells export TERMINAL_BG from ~/.terminal-bg →
  tmux reads ~/.terminal-bg on attach/startup →
  nvim watcher fires if file changed → vim.o.background updates
```

For mid-session changes (rare — typically once per day):

```psuedo
User runs `bglight` or `bgdark` →
  helper updates ~/.terminal-bg, ~/.claude.json, and ~/.codex/config.toml →
  nvim watcher fires immediately →
  sets tmux env → new shells get updated TERMINAL_BG →
  sets current shell env → next delta/git invocation uses new theme
```

### File Changes Summary

| File                                                 | Action           | Notes                                                                                                               |
| ---------------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------- |
| `chezmoi/dot_config/tmux/tmux.conf.tmpl`             | **Create**       | New tmux config                                                                                                     |
| `chezmoi/dot_zshrc.tmpl`                             | **Modify**       | Replace ideoc/ide (zellij→tmux), drop `_maybe_refresh_terminal_bg`, and read `TERMINAL_BG` from `~/.terminal-bg`   |
| `ansible/roles/terminal_theme/files/tmux-theme.zsh`  | **Create**       | Shared `bglight`/`bgdark` helper that updates tmux state via one function                                           |
| `ansible/roles/terminal_theme/files/terminal-theme-switch.py` | **Create** | Centralizes theme side effects for tmux hooks and the LaunchAgent watcher                                            |
| `ansible/roles/terminal_theme/files/terminal-theme-watch` | **Create**   | `dark-notify` wrapper that forwards appearance changes into the shared helper                                        |
| `ansible/roles/terminal_theme/templates/house.thurstons.terminal-theme-watch.plist.j2` | **Create** | LaunchAgent that keeps the watcher running on macOS                                                                  |
| `ansible/roles/terminal_theme/tasks/main.yml`        | **Create**       | Installs scripts, seeds `~/.terminal-bg`, and reloads the LaunchAgent when inputs change                            |
| `chezmoi/dot_config/zellij/`                         | **Keep for now** | Don't remove until tmux is validated; ignore via `.chezmoiignore` if needed                                         |
| `chezmoi/dot_config/nvim/lua/config/autocmds.lua`    | **No change**    | File watcher on `~/.terminal-bg` stays as-is                                                                        |
| `chezmoi/dot_config/nvim/lua/config/options.lua`     | **Modify**       | `TERMINAL_BG` env var read at startup stays; window title now reflects cwd                                           |
| `chezmoi/dot_config/nvim/lua/plugins/ghostty-navigator.lua` | **Add**    | Local macOS navigation now goes through `ghostty-nav`; `vim-tmux-navigator` is disabled there                       |
| `chezmoi/dot_config/git/config.tmpl`                 | **No change**    | `--${TERMINAL_BG:-dark}` delta config unchanged                                                                     |
| `chezmoi/.chezmoi.toml.tmpl`                         | **No change**    | Delta pager config unchanged                                                                                        |
| `chezmoi/.chezmoiignore`                             | **Maybe modify** | Add zellij config to ignore if removing from deployment                                                             |
| `chezmoi/dot_config/zellij/layouts/openclaw-ide.kdl` | **Keep**         | Don't delete until tmux is fully validated                                                                          |

### nvim Plugin Addition

Remote tmux workflows still assume tmux-aware navigation, but the current local macOS config now loads a Ghostty-native navigator plugin instead:

```lua
-- chezmoi/dot_config/nvim/lua/plugins/ghostty-navigator.lua
local ghostty_nav = require("lib.ghostty-nav")

ghostty_nav.setup()

return {
  { "christoomey/vim-tmux-navigator", enabled = false },
  {
    dir = ".",
    name = "ghostty-navigator",
    keys = {
      { "<C-h>", function() ghostty_nav.navigate("h", "left") end, desc = "Navigate Left" },
      { "<C-j>", function() ghostty_nav.navigate("j", "down") end, desc = "Navigate Down" },
      { "<C-k>", function() ghostty_nav.navigate("k", "up") end, desc = "Navigate Up" },
      { "<C-l>", function() ghostty_nav.navigate("l", "right") end, desc = "Navigate Right" },
    },
  },
}
```

See `docs/designs/07-ghostty-btt-navigator.md` for the full Ghostty-native design.

### macOS Considerations

The tmux config still works on both platforms. Platform-specific differences:

- macOS already has tmux via Homebrew; clawdbot has it via apt
- macOS theme state is now maintained by the Ansible-managed `terminal_theme` role and its LaunchAgent
- The local macOS `ide()` flow now uses Ghostty-native split management via `ghostty-nav`
- `ideoc()` on clawdbot remains tmux-based
- local macOS navigation no longer depends on `vim-tmux-navigator`

### Migration Steps

1. Create tmux.conf template in chezmoi
2. Keep remote tmux navigation intact while local macOS navigation moves to `ghostty-nav`
3. Modify `.zshrc` template (ideoc/ide rewrite, drop precmd hook, add bglight/bgdark)
4. Deploy the macOS theme manager via the Ansible `terminal_theme` role
5. Test: clipboard, links, theme detection, pane navigation, scratch popup
6. If validated, add zellij config paths to `.chezmoiignore`
7. Deploy to macOS and validate both `ide()` and the LaunchAgent-driven theme sync

### Open Questions

- Whether pane border labels should stay enabled long-term, or be simplified once the workflow settles
- Whether the theme helper should remain Claude/Codex-specific, or grow to manage more terminal-aware tools such as Pi
