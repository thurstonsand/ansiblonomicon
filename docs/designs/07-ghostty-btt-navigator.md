# Ghostty Native Navigator Plan

## Problem Statement

We want `vim-tmux-navigator`-style movement (`Ctrl-h/j/k/l`) while migrating away from tmux and using Ghostty splits natively.

Ghostty now has the missing primitive: key tables. They are activated per surface, not globally, which is enough to let a Neovim surface behave differently from neighboring shell surfaces.

## Design

### High-Level Architecture

1. Ghostty owns `Ctrl-h/j/k/l` by default and uses them for `goto_split:*`.
2. Neovim activates a Ghostty `nvim` key table on its own surface.
3. In that table, Ghostty passes raw control bytes through to the PTY.
4. Neovim handles local window movement first.
5. At a Neovim edge, Neovim calls a tiny `ghostty-nav` helper to ask Ghostty to move to the adjacent split.
6. When Neovim exits or suspends, it deactivates the key table.
7. A shell precmd hook repairs stale state if Neovim crashes and leaves a per-TTY sentinel behind.

No HTTP server. No title markers. No BetterTouchTool. No shell in the keypress hot path.

### Ghostty Configuration

Default table:

- `ctrl+h/j/k/l = goto_split:*`

`nvim` key table:

- `ctrl+h/j/k/l = text:\x08/\x0a/\x0b/\x0c`

Key tables are explicitly activated with `activate_key_table:<name>` and deactivated with `deactivate_key_table`.

### Neovim Lifecycle

Neovim is the source of truth for whether its surface should be in the `nvim` key table.

Autocommands:

- `VimEnter` → activate `nvim`
- `VimResume` → activate `nvim`
- `VimSuspend` → deactivate
- `VimLeavePre` → deactivate

The same hooks create and remove a per-TTY sentinel in `~/.local/state/ghostty-nav/`.

### Recovery Path

If Neovim crashes or is killed before cleanup runs, the shell prompt hook checks for a sentinel for the current `$TTY`.

If present:

1. run `ghostty-nav deactivate`
2. remove the sentinel

Normal shell prompts do only a file existence check.

### Helper CLI

`ghostty-nav` is a small argv-based Swift CLI that owns Ghostty-side actions for both navigation and local tab shaping:

- `ghostty-nav activate nvim`
- `ghostty-nav deactivate`
- `ghostty-nav move left|down|up|right`
- `ghostty-nav tab-terminal-count`
- `ghostty-nav split <left|right|up|down> [--cwd <path>] [--command <string>] [--focus <new|original>]`
- `ghostty-nav resize <left|down|up|right> (--pixels <n> | --percent <n>)`
- `ghostty-nav toggle-zoom`
- `ghostty-nav title <text>`

On macOS the split/navigation actions talk to Ghostty via `NSAppleScript`, while `title` writes OSC 2 directly to the current TTY so shell wrappers can retitle the active Ghostty surface without carrying their own escape-sequence logic.

### Local IDE Flow

The local `ide()` shell function is now intentionally narrow:

1. Require Ghostty and a fresh tab with exactly one terminal.
2. Split left and start a fresh interactive/login shell there.
3. Launch `nvim .` inside that new left shell.
4. Keep the original shell on the right, optionally running a user-supplied command.
5. Resize the right split to 15% and zoom the editor split.

This avoids the older per-project window registry, bootstrap environment variables, and inline AppleScript from shell config.

## Implementation Notes

### Why this works

This matches the same general contract as `vim-tmux-navigator`:

1. local editor movement first
2. outer container movement second
3. pane-local state, not global state

The difference is that tmux can inspect pane state itself, while Ghostty needs Neovim to switch key tables explicitly.

### Why the sentinel is per TTY

A global sentinel would break as soon as one Ghostty split was running Neovim and another was running a shell. Per-TTY state keeps the repair local to the surface that needs it.

## Testing Matrix

1. Shell surface: `Ctrl-h/j/k/l` moves Ghostty splits.
2. Neovim surface with internal splits: `Ctrl-h/j/k/l` moves inside Neovim.
3. Neovim surface at an edge: `Ctrl-h/j/k/l` falls through to Ghostty split navigation.
4. Suspend Neovim with `Ctrl-z`: shell regains normal Ghostty bindings.
5. Resume Neovim with `fg`: `nvim` key table is reactivated.
6. Kill Neovim badly: next shell prompt repairs Ghostty state for that `$TTY`.

## Success Criteria

1. `Ctrl-h/j/k/l` feels continuous between Neovim and Ghostty splits.
2. No tmux dependency for local split navigation.
3. No BTT dependency.
4. No HTTP daemon or title-marker routing.
5. Failure recovery is local, cheap, and predictable.
