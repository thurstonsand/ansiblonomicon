# Neovim capability

Native mise owns Neovim configuration directly. Static files use `symlink-each`, preserving unknown children under `~/.config/nvim`; host-sensitive Lua files are rendered as regular files. Lockfiles are deliberately outside the shared tree: personal hosts symlink `lazy-lock.json` writable-back to the repository, while work receives a copy of `lazy-lock.work.json` that every reconcile restores. Work's separate pins preserve its Ansible and chezmoi plugins when personal Lazy sync removes those plugins. Personal retirements remove their old Mason packages and launcher links.

Sources live in `bootstrap/capabilities/neovim/files/`; each registered target exposes that directory as `neovim/` beside its mise environment files.

Run `mise neovim` (alias `mise nvim-deps`) to apply configuration and then preserve the former dependency sequence: personal Lazy sync (work Lazy restore), broken Mason Python-venv cleanup, personal-only `MasonToolsUpdateSync`, and Treesitter update. `mise neovim --check`, or native `mise bootstrap dotfiles apply --force --dry-run` in the target with the Neovim environments selected, previews configuration and never upgrades dependencies. Software remains in the existing Brewfiles and pod042 operator capability.

The work target requires private `neovim_jira_browse_url`, `neovim_scm_remote_patterns`, and `neovim_scm_url_patterns` variables in its ignored `mise.local.toml`; there are no internal defaults. See `README.work.md` for the exact old-to-new mapping.
