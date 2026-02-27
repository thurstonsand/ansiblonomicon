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

### tmux.conf

Chezmoi-managed at `chezmoi/dot_config/tmux/tmux.conf.tmpl`. Platform-specific sections use chezmoi conditionals where needed.

#### Core Settings

```tmux
# Terminal compatibility
set -g default-terminal "tmux-256color"
set -g allow-passthrough all
set -ga terminal-features ",*:hyperlinks"
set -s set-clipboard on
set -s extended-keys on
set -s escape-time 0
set -g focus-events on

# Behavior
set -g mouse on
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on
set -g history-limit 50000
set -g mode-keys vi
set -g status-keys vi
```

#### Theme: Inherit from Ghostty

No explicit color theme. Use `default` to inherit terminal colors for status bar and borders. This means Ghostty's gruvbox light/dark theme controls the overall look, and tmux stays transparent.

```tmux
set -g status-style 'bg=default,fg=default'
set -g pane-border-style 'fg=default'
set -g pane-active-border-style 'fg=default'
set -g message-style 'bg=default,fg=default'
set -g status-position bottom
```

#### Alt-Key Bindings (Root Table)

No prefix required. These occupy a namespace that doesn't conflict with nvim or coding agents.

```tmux
# Window switching
bind -n M-1 select-window -t :=1
bind -n M-2 select-window -t :=2
bind -n M-3 select-window -t :=3
bind -n M-4 select-window -t :=4
bind -n M-5 select-window -t :=5

# Pane navigation (overridden by vim-tmux-navigator for seamless nvim integration)
bind -n M-h select-pane -L
bind -n M-j select-pane -D
bind -n M-k select-pane -U
bind -n M-l select-pane -R

# Pane/window management
bind -n M-z resize-pane -Z          # zoom toggle
bind -n M-n new-window
bind -n M-x confirm-before -p "kill pane? (y/n)" kill-pane

# Floating scratch session
bind -n M-f if-shell -F '#{==:#{session_name},scratch}' {
    detach-client
} {
    display-popup -w 80% -h 80% -E "tmux new -As scratch"
}

# Copy mode
bind -n M-[ copy-mode
```

#### vim-tmux-navigator Integration

Seamless C-hjkl navigation between nvim splits and tmux panes. Requires the nvim plugin (`christoomey/vim-tmux-navigator`) and corresponding tmux bindings. The standard integration uses `C-h/j/k/l` for navigation and `C-\` for previous pane.

```tmux
# Smart pane switching with awareness of Vim splits
is_vim="ps -o state= -o comm= -t '#{pane_tty}' | grep -iqE '^[^TXZ ]+ +(\\S+\\/)?g?(view|l?n?vim?x?|fzf)(diff)?$'"
bind -n C-h if-shell "$is_vim" 'send-keys C-h' 'select-pane -L'
bind -n C-j if-shell "$is_vim" 'send-keys C-j' 'select-pane -D'
bind -n C-k if-shell "$is_vim" 'send-keys C-k' 'select-pane -U'
bind -n C-l if-shell "$is_vim" 'send-keys C-l' 'select-pane -R'
bind -n C-\\ if-shell "$is_vim" 'send-keys C-\\\\' 'select-pane -l'
```

### Session Management: `ideoc()` Function

Replaces the current Zellij-based `ideoc()` in `dot_zshrc.tmpl`. Creates or attaches to the `openclaw` tmux session with two windows.

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

  # Detect terminal background BEFORE entering tmux (OSC 11 works here)
  export TERMINAL_BG=$(_detect_terminal_bg)

  if [[ "$1" == "--recreate" ]]; then
    tmux kill-session -t "$session" 2>/dev/null
  fi

  if tmux has-session -t "$session" 2>/dev/null; then
    # Session exists — update env and attach
    tmux set-environment -t "$session" TERMINAL_BG "$TERMINAL_BG"
    tmux attach -t "$session"
  else
    # Create new session with two windows
    tmux new-session -d -s "$session" -n ansiblonomicon -c ~/code/ansiblonomicon
    tmux split-window -v -t "$session":ansiblonomicon -c ~/code/ansiblonomicon
    tmux new-window -t "$session" -n home -c ~
    tmux split-window -v -t "$session":home -c ~
    tmux set-environment -t "$session" TERMINAL_BG "$TERMINAL_BG"
    tmux select-window -t "$session":ansiblonomicon
    tmux select-pane -t 0
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

| Component                      | Before (Zellij)           | After (tmux)                                                                   |
| ------------------------------ | ------------------------- | ------------------------------------------------------------------------------ |
| `_detect_terminal_bg()`        | No change                 | No change — runs before tmux, OSC 11 works                                     |
| `_maybe_refresh_terminal_bg()` | Runs in precmd every 300s | **Removed** — OSC 11 can't round-trip inside tmux                              |
| Source of truth                | `~/.terminal-bg` file     | `~/.terminal-bg` file (for nvim watcher) + `tmux set-environment` (for shells) |
| nvim file watcher              | Watches `~/.terminal-bg`  | **Kept unchanged** — reacts to bglight/bgdark writes                           |
| nvim FocusGained               | Not used                  | Not needed — file watcher is more responsive                                   |

#### `bglight` / `bgdark` Functions

Manual override for mid-session theme changes. Each function updates all three consumers:

```zsh
bglight() {
  echo "light" > ~/.terminal-bg           # triggers nvim file watcher
  tmux set-environment TERMINAL_BG light 2>/dev/null  # new shells inherit
  export TERMINAL_BG=light                # current shell (delta/git)
}

bgdark() {
  echo "dark" > ~/.terminal-bg
  tmux set-environment TERMINAL_BG dark 2>/dev/null
  export TERMINAL_BG=dark
}
```

#### Detection Flow

```
macOS theme changes → Ghostty updates colors →
  (next SSH connection) →
  zsh starts → _detect_terminal_bg() runs (no tmux yet, OSC 11 works) →
  ideoc() sets tmux env + writes file →
  tmux attach → nvim watcher fires if file changed → vim.o.background updates
```

For mid-session changes (rare — typically once per day):

```psuedo
User runs `bglight` or `bgdark` →
  writes ~/.terminal-bg → nvim watcher fires immediately →
  sets tmux env → new shells get updated TERMINAL_BG →
  sets current shell env → next delta/git invocation uses new theme
```

### File Changes Summary

| File                                                 | Action           | Notes                                                                                                               |
| ---------------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------- |
| `chezmoi/dot_config/tmux/tmux.conf.tmpl`             | **Create**       | New tmux config                                                                                                     |
| `chezmoi/dot_zshrc.tmpl`                             | **Modify**       | Replace ideoc/ide (zellij→tmux), drop `_maybe_refresh_terminal_bg`, add bglight/bgdark, change `$ZELLIJ` to `$TMUX` |
| `chezmoi/dot_config/zellij/`                         | **Keep for now** | Don't remove until tmux is validated; ignore via `.chezmoiignore` if needed                                         |
| `chezmoi/dot_config/nvim/lua/config/autocmds.lua`    | **No change**    | File watcher on `~/.terminal-bg` stays as-is                                                                        |
| `chezmoi/dot_config/nvim/lua/config/options.lua`     | **No change**    | `TERMINAL_BG` env var read at startup stays                                                                         |
| `chezmoi/dot_config/nvim/lua/plugins/`               | **Add**          | vim-tmux-navigator plugin spec                                                                                      |
| `chezmoi/dot_config/git/config.tmpl`                 | **No change**    | `--${TERMINAL_BG:-dark}` delta config unchanged                                                                     |
| `chezmoi/.chezmoi.toml.tmpl`                         | **No change**    | Delta pager config unchanged                                                                                        |
| `chezmoi/.chezmoiignore`                             | **Maybe modify** | Add zellij config to ignore if removing from deployment                                                             |
| `chezmoi/dot_config/zellij/layouts/openclaw-ide.kdl` | **Keep**         | Don't delete until tmux is fully validated                                                                          |

### nvim Plugin Addition

Add vim-tmux-navigator to the LazyVim config:

```lua
-- chezmoi/dot_config/nvim/lua/plugins/tmux-navigator.lua
return {
  "christoomey/vim-tmux-navigator",
  cmd = {
    "TmuxNavigateLeft",
    "TmuxNavigateDown",
    "TmuxNavigateUp",
    "TmuxNavigateRight",
    "TmuxNavigatePrevious",
  },
  keys = {
    { "<C-h>", "<cmd>TmuxNavigateLeft<cr>" },
    { "<C-j>", "<cmd>TmuxNavigateDown<cr>" },
    { "<C-k>", "<cmd>TmuxNavigateUp<cr>" },
    { "<C-l>", "<cmd>TmuxNavigateRight<cr>" },
    { "<C-\\>", "<cmd>TmuxNavigatePrevious<cr>" },
  },
}
```

### macOS Considerations

The tmux config works on both platforms. Platform-specific differences:

- macOS already has tmux via Homebrew; clawdbot has it via apt
- `_detect_terminal_bg()` runs locally on macOS (no SSH, always works)
- The `ide()` function (macOS) follows the same tmux pattern as `ideoc()` (clawdbot)
- vim-tmux-navigator works identically on both platforms

### Migration Steps

1. Create tmux.conf template in chezmoi
2. Add vim-tmux-navigator nvim plugin
3. Modify `.zshrc` template (ideoc/ide rewrite, drop precmd hook, add bglight/bgdark)
4. Deploy via `chezmoi apply` on clawdbot
5. Test: clipboard, links, theme detection, pane navigation, scratch popup
6. If validated, add zellij config paths to `.chezmoiignore`
7. Deploy to macOS and validate `ide()` function

### Open Questions

- Should the Alt-key pane navigation (M-hjkl) coexist with vim-tmux-navigator's C-hjkl, or should one replace the other?
- Should `ide()` on macOS also switch from Zellij to tmux, or keep Zellij where it works fine?
- Pane border status (`pane-border-status top` with pane titles) — worth enabling for visual identification of editor vs agent panes?
- Should TPM be used for vim-tmux-navigator's tmux-side bindings, or inline them directly in tmux.conf?
