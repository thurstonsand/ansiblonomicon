# Ghostty + BetterTouchTool Navigator Plan

## Problem Statement

We want `vim-tmux-navigator`-style movement (`Ctrl-h/j/k/l`) while migrating away from tmux and using Ghostty splits natively.

Current constraint: Ghostty cannot natively do process-aware key routing (`if nvim then send ctrl-h else goto_split:left`).

Ghostty provides:

1. Split actions (`goto_split`, `new_split`, `resize_split`, `toggle_split_zoom`)
2. AppleScript control of focused window/tab/terminal
3. `send key` and `perform action` commands

Ghostty does **not** provide:

1. Foreground process query for a pane
2. Conditional keybind actions based on pane process

## Goals

1. Seamless `Ctrl-h/j/k/l` behavior across Neovim and Ghostty splits
2. Keep Ghostty as the only local multiplexer (no tmux dependency)
3. Use BetterTouchTool (BTT) as the key-router layer on macOS
4. Preserve existing window-manager shortcuts (Rectangle) and normal shell behavior
5. Keep behavior debuggable and easy to roll back

## Non-Goals

1. Implementing process-aware routing inside Ghostty itself
2. Linux/GTK parity in this phase
3. Full remote-session integration in this phase

## Design

### High-Level Architecture

Key routing becomes a 3-layer flow:

1. **BTT layer** captures `Ctrl-h/j/k/l` globally (or app-scoped to Ghostty)
2. **Router script** decides whether current Ghostty terminal is in Neovim context
3. **Action execution**:
   1. If Neovim context: forward `Ctrl-h/j/k/l` to terminal
   2. Else: run Ghostty `goto_split:left/down/up/right`

Important edge-case behavior:

1. If Neovim is focused and navigation is at Neovim edge (e.g. right-most split + `Ctrl-l`), the flow must fall back to Ghostty split navigation.
2. This requires Neovim-side edge detection plus an unconditional Ghostty move command path.

### Neovim Context Signal

Because Ghostty does not expose foreground process names, use terminal title signaling:

1. Neovim sets title (OSC 2) with a zero-width space (U+200B) prefix, e.g. `\u200B<file>`
2. Router checks `name of focused terminal` via Apple Events
3. Prefix match on U+200B indicates Neovim context — invisible in the title bar

Shell integration should restore title when returning to prompt so stale markers do not linger.

### Router Script Contract

Create `~/.local/bin/ghostty-nav` with interface:

```sh
ghostty-nav left|down|up|right
ghostty-nav --ghostty-only left|down|up|right
```

Behavior:

1. Validate direction argument
2. Query focused Ghostty terminal title
3. If `--ghostty-only` is set:
   1. Always run `perform action "goto_split:<dir>"` on focused terminal
4. Else if title starts with U+200B (zero-width space):
   1. Send control key (`h/j/k/l`) to focused terminal
5. Else:
   1. `perform action "goto_split:<dir>"` on focused terminal

Return code:

1. `0` on handled
2. non-zero for no Ghostty window/focus or script error

Neovim must call `ghostty-nav --ghostty-only <dir>` on edge fallback to avoid routing loops.

### Neovim Edge Fallback Contract

Neovim mappings should use this pattern:

1. Attempt normal `wincmd h/j/k/l`
2. If current Neovim window did not change, call `ghostty-nav --ghostty-only <dir>`

This guarantees expected behavior when focused on edge-most Neovim windows while still preserving native Neovim split movement.

### BetterTouchTool Bindings

Add four BTT shortcuts using "Run Apple Script (in Background)" with pre-compiled `.scpt` files:

1. `Ctrl-h` → `~/.local/share/ghostty-nav/nav-left.scpt`
2. `Ctrl-j` → `~/.local/share/ghostty-nav/nav-down.scpt`
3. `Ctrl-k` → `~/.local/share/ghostty-nav/nav-up.scpt`
4. `Ctrl-l` → `~/.local/share/ghostty-nav/nav-right.scpt`

The `.scpt` files run in BTT's in-process AppleScript runtime (no process spawn). The Swift binary at `~/.local/bin/ghostty-nav` is used only by Neovim for edge-fallback navigation.

Scope options:

1. Preferred: app-specific to Ghostty
2. Alternate: global with app check in script

### Ghostty Keybind Strategy

Keep explicit Ghostty-native fallback navigation on separate chords for debugging/manual use.

Current directional fallback candidates:

1. `cmd+opt+arrow` for `goto_split:*`
2. `cmd+[ / cmd+]` for previous/next split

Do not bind `Ctrl-h/j/k/l` inside Ghostty config in this design; BTT owns those keys.

### Prefix Language for Creation Actions

Maintain a consistent pane-management prefix in Ghostty config:

1. `cmd+shift+a>z` → `toggle_split_zoom`
2. `cmd+shift+a>-` / `cmd+shift+a>minus` → `new_split:down`
3. `cmd+shift+a>/` → `new_split:right`

This keeps creation/zoom semantics mnemonic and separate from movement semantics.

## Implementation Plan

### Phase 1: Script + Manual Validation

1. Add `ghostty-nav` script (local bin)
2. Add Neovim title signal (`NVIM:...`)
3. Validate manually in Ghostty:
   1. In shell pane, `ghostty-nav left/right/up/down` moves Ghostty focus
   2. In Neovim pane, `ghostty-nav left/right/up/down` sends control keys to Neovim
   3. `ghostty-nav --ghostty-only left/right/up/down` always moves Ghostty focus regardless of title

### Phase 2: BetterTouchTool Wiring

1. Add BTT shortcuts for `Ctrl-h/j/k/l`
2. Scope shortcuts to Ghostty app
3. Validate no conflicts with system/global shortcuts

### Phase 3: Neovim Edge Behavior

1. Add/verify Neovim mappings so `Ctrl-h/j/k/l` do split nav internally
2. Confirm at-edge behavior transitions via Neovim edge fallback to `ghostty-nav --ghostty-only`
3. Confirm shell panes receive Ghostty movement, not control-character noise

### Phase 4: Harden + Document

1. Add concise notes in dotfiles comments and/or docs
2. Add rollback command snippets (disable BTT trigger group)
3. Capture known caveats

## Testing Matrix

1. Ghostty with single pane: router should pass through or no-op safely
2. Ghostty with multiple splits, shell focused: router moves Ghostty split focus
3. Ghostty with Neovim focused and Neovim internal split exists: key stays in Neovim
4. Ghostty with Neovim focused at split edge: Neovim fallback should call `--ghostty-only` and move Ghostty split
5. After exiting Neovim: title signal clears; router returns to Ghostty movement mode
6. App not Ghostty frontmost: BTT app-scoped triggers should not fire

## Risks and Mitigations

1. **Title desync**: Neovim marker persists after exit
   1. Mitigation: ensure shell integration/title restoration is active
2. **Automation permission prompts**
   1. Mitigation: pre-grant BTT/osascript automation permissions
3. **Latency from per-key AppleScript**
   1. Mitigation: keep script minimal; app-scope triggers; if needed, move to long-lived helper later
4. **Key collision with terminal usage**
   1. Mitigation: constrain to Ghostty and document fallback keys
5. **Router loop on Neovim edge**
   1. Mitigation: enforce Neovim fallback path uses `ghostty-nav --ghostty-only` rather than context-aware mode

## Rollback Plan

1. Disable BTT trigger group for `Ctrl-h/j/k/l`
2. Keep using explicit Ghostty pane movement keys (`cmd+opt+arrow`, `cmd+[`, `cmd+]`)
3. Remove Neovim title marker if no longer needed

## Success Criteria

1. `Ctrl-h/j/k/l` feels continuous between Neovim and Ghostty panes
2. No tmux dependency for local navigation
3. No regression in existing pane creation/zoom workflows
4. Behavior is reversible in under one minute via BTT toggle
