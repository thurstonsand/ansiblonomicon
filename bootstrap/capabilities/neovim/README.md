# Neovim capability

Native mise owns Neovim configuration directly. Static files use `symlink-each`, preserving unknown children under `~/.config/nvim`; host-sensitive Lua files are rendered as regular files. Lockfiles are deliberately outside the shared tree: personal hosts symlink `lazy-lock.json` writable-back to the repository, while work receives a copy of `lazy-lock.work.json` that every reconcile restores. Work keeps its own pins, independent of personal Lazy sync.

Sources live in `bootstrap/capabilities/neovim/files/`; each registered target exposes that directory as `neovim/` beside its mise environment files.

Run `mise neovim` (alias `mise nvim-deps`) to apply configuration and then run the dependency sequence: personal Lazy sync (work Lazy restore), broken Mason Python-venv cleanup, personal-only `MasonToolsUpdateSync`, and Treesitter update. `mise neovim --check`, or native `mise bootstrap dotfiles apply --force --dry-run` in the target with the Neovim environments selected, previews configuration and never upgrades dependencies. Neovim itself is installed by the Brewfiles and the pod042 operator capability.

## Omarchy

On type-a-no2, the repo shares `~/.config/nvim` with the config Omarchy seeds from `/usr/share/omarchy-nvim/config`, shadowing it in place. The repo owns `init.lua`, `lazyvim.json`, `stylua.toml`, `lua/config/*`, and its own plugin specs. Omarchy keeps the files only it ships (`all-themes.lua`, `theme.lua`, `omarchy-theme-hotreload.lua`, and friends). `remote_clipboard.lua` is vendored from Omarchy, so every host gets the same clipboard. `colorscheme.lua.tera` renders nothing under Omarchy, which leaves the colorscheme to Omarchy's theme engine. Elsewhere it renders gruvbox with the terminal-background watcher. Omarchy's plugin set differs from the shared pins, so it gets its own `lazy-lock.omarchy.json`.

Omarchy edits its files in place through migrations, so `mise neovim` on that host also runs `neovim:omarchy-drift`, which exits 1 when:

- a file the repo shadows changed in the Omarchy package. Diff it against the repo, port what's worth keeping, then record it with `mise -C bootstrap/targets/type-a-no2 run neovim:omarchy-drift --update` (with `MISE_ENV=neovim,neovim-omarchy`).
- an Omarchy-owned file no longer matches the package. The finding prints the `cp` that reseeds it.
- a regular file sits in `lua/config` or `lua/plugins` that neither side declares.

A migration that `mv`s over a repo-owned symlink makes `mise neovim --check` fail on the conflict before the drift task runs. Port its change into the repo, then reapply with `--force` from the target directory.

The work target requires private `neovim_jira_browse_url`, `neovim_scm_remote_patterns`, and `neovim_scm_url_patterns` variables in its ignored `mise.local.toml`; there are no internal defaults. See `README.work.md` for their shapes.
