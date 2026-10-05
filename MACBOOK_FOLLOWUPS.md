# MacBook follow-ups

Changes made from the Omarchy laptop that the MacBooks still need to reconcile or decide on.

1. **Retirements:** OpenCode, Gemini CLI, Cursor, Windsurf, Devin Desktop, and Antigravity were removed from the repo. The MacBooks still carry their installed state, and the repo carries temporary retirement declarations until both have reconciled.
2. **Shell:** `zshrc.tera` now adopts Omarchy's defaults everywhere:
   - history with `HIST_IGNORE_ALL_DUPS`
   - eza `ls`/`lsa`/`lt`/`lta`
   - a `cd` that runs through zoxide's `zd` wrapper (work keeps autojump)
   - `top` mapped to `btop`, with `btop` replacing `htop` in both Brewfiles
   - Starship truncating the path to 2 levels and showing git branch and status as glyphs
3. **Hunk in Neovim:** the `<leader>gV` Hunk float and its `~/.local/libexec/hunk/nvim` editor helper were removed. `user-tools` retires the helper with a `state = "absent"` file declaration.
4. **Evalcache:** `_evalcache` is now macOS-only. On Linux it saved about 10ms per shell (36.6ms cached vs 46.3ms plain eval over 40 interleaved runs), which did not justify its complexity. macOS starts processes more slowly, so it needs its own measurement.

## Personal MacBook (`Thurstons-MacBook-Pro`)

1. `mise run pull`
2. `rm -f ~/.cache/ansiblonomicon/homebrew-upgrade.stamp && mise laptop -t agent-harness,homebrew,editor-config,shell,user-tools,neovim` (cask and formula cleanup only runs when the daily stamp is due)
   - `agent-harness` retires the OpenCode plugin layout (`harnesses/opencode/mise.toml`) and the OpenCode and `~/.gemini` `[[absent]]` paths in `configuration/assets.toml`.
   - `homebrew` uninstalls the `opencode-desktop`, `cursor`, `antigravity`, and `devin-desktop` casks and the `gemini-cli` and `htop` formulae, and installs `visual-studio-code` and `btop`.
   - `editor-config` writes VS Code's `settings.json` and `keybindings.json` under `~/Library/Application Support/Code/User/`.
   - `shell` renders the new `.zshrc` and `.zshenv`; Starship's config is a symlink and is already current.
3. Verify that none of these exist, and remove any that do: `~/.opencode`, `~/.config/opencode`, `~/.local/share/opencode`, `~/.local/state/opencode`, `~/.cache/opencode`, `~/.gemini`, and `~/Library/Application Support/{Cursor,Windsurf,Antigravity}/User/{settings,keybindings}.json` (dangling links left by the old editor-config).
4. Check that `command -v opencode gemini` prints nothing, and that a new shell shows the new `ls`, `cd`, and `top` aliases and prompt without errors.
5. Measure `_evalcache`. Build two scratch files from the `_evalcache` lines the rendered `~/.zshrc` runs: one that sources the `_evalcache` function from `~/.zshenv` and calls it, and one using plain `eval "$(cmd args)"`. Time `zsh -fc "source <file>"` from `$HOME` over 40 interleaved runs and compare medians. Report the numbers to Thurston. If the saving is small, drop the darwin `_evalcache` branch in `zshenv.tera` so every host uses the plain-eval passthrough, and delete `~/.cache/zsh/*_init.zsh*`.

## Work MacBook (`ML-DFC6YK6VJQ`)

1. `mise run pull`
2. `mise laptop -t agent-harness,shell,user-tools,neovim`, then `homebrew` with its stamp removed as above to swap `htop` for `btop`.
3. Verify the OpenCode paths and `~/.gemini` from step 3 above are gone, and that a new shell starts cleanly with autojump's `cd`.

## Self-destruct

Once Thurston confirms that both MacBooks have run this and decided on `_evalcache`, delete:

- this file
- the `## Pending: MacBook follow-ups` section in `AGENTS.md`
- the `MACBOOK_FOLLOWUPS.md` reference in `bootstrap/capabilities/shell/files/zshenv.tera`
- `bootstrap/capabilities/agent-harness/harnesses/opencode/mise.toml`
- the `~/.local/libexec/hunk/nvim` absent declaration in `bootstrap/capabilities/user-tools/mise.toml` (pod042 has applied it too)
- the OpenCode and `.gemini` `[[absent]]` entries in `bootstrap/capabilities/agent-harness/configuration/assets.toml`
