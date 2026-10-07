# Session-recovery follow-ups

`refactor!: retire session recovery and the sessions CLI` deleted the recovery tree and the `sessions` CLI from the repo. The work Mac reconciled it on 2026-10-06 and pod042 on 2026-10-07. The other two hosts still carry the installed state, and the repo carries temporary retirement declarations until they have all reconciled.

Two things the work Mac taught us:

- Claude hook ownership tracking (e3cacd3) is newer than the recorder's hooks, so `agent-config` keeps them in `~/.claude/settings.json` as if you had added them yourself. After reconciling, `grep -c session-recovery ~/.claude/settings.json` must print `0`. If it doesn't, delete those hook groups by hand; nothing re-adds them. Also check the host's gitignored `bootstrap/capabilities/agent-harness/local/<hostname>/claude-settings-overlay.json`, if it exists, for recorder hooks.
- A pi or Claude session that was already running keeps the old recorder loaded and recreates `~/.local/state/session-recovery`. Restart them all after reconciling, then check the paths again.

## Personal MacBook (`Thurstons-MacBook-Pro`)

1. `mise run pull`
2. `mise laptop -t agent-config,shell,uvc-util,terminal-tools,neovim`
   - `agent-config` removes the recorder trees, their config, and the recovery state, and drops the recorder hooks it still knows it owns.
   - `shell` deletes the cached `sessions` completions, and `uvc-util` deletes `~/.local/bin/sessions` and its build stamps.
   - `terminal-tools` and `neovim` drop the dead `ide-<name>-<hex>` session-name parsing.
3. Do the Claude hook check above, and restart running agents.
4. Check that `command -v sessions` prints nothing, and that none of these exist: `~/.claude/scripts/session-recovery`, `~/.config/session-recovery`, `~/.local/lib/session-recovery`, `~/.local/state/session-recovery`, `~/.pi/agent/extensions/session-recovery`, `~/.cache/ansiblonomicon/sessions`, and `~/.cache/zsh/sessions_*`.

## Omarchy laptop (`type-a-no2`)

1. `git pull`
2. `mise omarchy -t agent-config,shell`
3. Do the Claude hook check above, restart running agents, and check the same paths as the personal MacBook's step 4.

## Self-destruct

Once Thurston confirms that both remaining hosts have run this, delete:

- this file
- the `## Pending: session-recovery follow-ups` section in `AGENTS.md`
- the five session-recovery `[[absent]]` entries in `bootstrap/capabilities/agent-harness/configuration/assets.toml`
- the four `~/.cache/zsh/sessions_*` absent declarations in `bootstrap/capabilities/shell/mise.toml`
- the `~/.local/bin/sessions` and `~/.cache/ansiblonomicon/sessions` absent declarations in `bootstrap/capabilities/software/mise.files.toml`, then return the `uvc-util` task in `bootstrap/capabilities/software/mise.toml` from `--only files,dotfiles` to `--only dotfiles` in both of its `mise bootstrap` calls
- the `/home/thurstonsand/.local/bin/sessions` absent declaration in `bootstrap/targets/pod042/mise.operator.toml`
