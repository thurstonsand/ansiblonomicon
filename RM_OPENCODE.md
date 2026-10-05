# RM_OPENCODE

OpenCode, Gemini CLI, Cursor, Windsurf, Devin Desktop, and Antigravity were removed from the repo. The MacBooks still carry their installed state, and the repo carries temporary retirement declarations until both have reconciled.

## Personal MacBook (`Thurstons-MacBook-Pro`)

1. `mise run pull`
2. `rm -f ~/.cache/ansiblonomicon/homebrew-upgrade.stamp && mise laptop -t agent-harness,homebrew,editor-config` (cask cleanup only runs when the daily stamp is due)
   - `agent-harness` retires the OpenCode plugin layout (`harnesses/opencode/mise.toml`) and the OpenCode and `~/.gemini` `[[absent]]` paths in `configuration/assets.toml`.
   - `homebrew` uninstalls the `opencode-desktop`, `cursor`, `antigravity`, and `devin-desktop` casks and the `gemini-cli` formula, and installs `visual-studio-code`.
   - `editor-config` writes VS Code's `settings.json` and `keybindings.json` under `~/Library/Application Support/Code/User/`.
3. Verify that none of these exist, and remove any that do: `~/.opencode`, `~/.config/opencode`, `~/.local/share/opencode`, `~/.local/state/opencode`, `~/.cache/opencode`, `~/.gemini`, and `~/Library/Application Support/{Cursor,Windsurf,Antigravity}/User/{settings,keybindings}.json` (dangling links left by the old editor-config).
4. Check that `command -v opencode gemini` prints nothing.

## Work MacBook (`ML-DFC6YK6VJQ`)

1. `mise run pull`
2. `mise laptop -t agent-harness`
3. Verify the OpenCode paths and `~/.gemini` from step 3 above are gone.

## pod042

`mise pod042` also needs to run once before the retirement layout is deleted, so its OpenCode skills directory and `~/.gemini` are cleaned up. Remove any `gemini` or `opencode` binary installed there.

## Self-destruct

Once Thurston confirms that both MacBooks have run this, delete:

- this file
- the `## Pending: OpenCode removal` section in `AGENTS.md`
- `bootstrap/capabilities/agent-harness/harnesses/opencode/mise.toml`
- the OpenCode and `.gemini` `[[absent]]` entries in `bootstrap/capabilities/agent-harness/configuration/assets.toml`
