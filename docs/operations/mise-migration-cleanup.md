# Mise migration cleanup ledger

Track temporary compatibility and cutover code here as each capability migrates. Remove an item only after its exit condition is verified on every affected host, including the work laptop. A passing fixture is not a completed work-host cutover. Update this ledger in the same change that adds or removes migration machinery.

## Current rollout

| Capability | pod042 | Personal Mac | Work Mac |
| --- | --- | --- | --- |
| Terminal theme | Live, verified | Live, verified | Pending |
| Git client | Live, verified | Live, verified | Pending; private identity and SCM settings must be transferred |

## Delete after work cutover is verified

- [ ] **Legacy theme watcher retirement.** Remove `bootstrap.hooks.post-dotfiles` from `bootstrap/capabilities/terminal-theme/mise.macos.toml` and the old `house.thurstons.terminal-theme-watch.plist` absent declarations from both Mac targets' `mise.terminal-theme-files.toml`. First verify that the old job and plist are absent on work, exactly one `dev.mise.house.thurstons.terminal-theme-watch` job is loaded, light/dark switching works, and repeat apply does not restart it. Remove `test_legacy_watcher_is_unloaded_by_native_hook_once` and legacy-plist assertions from `tests/test_terminal_theme_capability.py`; retain native watcher lifecycle coverage. Remove the temporary cleanup explanation from the capability README.
- [ ] **Legacy Git adoption.** Remove the post-dotfiles hook from `bootstrap/capabilities/git-client/mise.toml`. Remove marker parsing, `LEGACY_OPTIONAL_KEYS`, `keys`, `remove_keys`, `adopt_file`, and `remove_legacy_global_include` from `files/adopt.py`; keep input validation in an appropriately named validation helper and update the pre-dotfiles hook. First verify work's effective configuration, corporate URL rewriting, personal-directory identity, signing, absence of duplicate managed keys outside the block, and absence of the old personal include in `~/.gitconfig`. Preserve unrelated settings in that file; do not delete it wholesale. Trim migration-specific fixtures/assertions in `tests/test_git_client_capability.py`, retaining tests for managed-block preservation of app keys, repeated values, validation, and no-op reconciliation. Update the capability README.
- [ ] **Forced dotfile takeover.** Recheck `--force-dotfiles` in the root `git-client` and `terminal-theme` tasks after all existing files have native ownership. Remove flags needed only to replace pre-migration regular files with symlinks, proving normal updates, fresh installation, and runtime-mutated Hunk rendering still work without them. Do not remove a flag merely because its name looks transitional.

## Delete only after remaining consumers migrate

- [ ] **Duplicated personal identity facts.** Remove `personalEmail` and `personalSigningKey` from `chezmoi/.chezmoidata.toml` after `chezmoi/dot_config/jj/config.toml.tmpl` migrates to the shared native identity facts. Work Git cutover alone is not sufficient. Move work's private identity facts only after its Jujutsu consumer migrates too.
- [ ] **Old work SCM data.** Retire `[[scm]]` in the work-only chezmoi data only after its remaining Neovim gitbrowse consumer migrates. Copying the Git URL rewrites into `git_scm_config` does not retire that other consumer.
- [ ] **Chezmoi ownership guards.** Remove the Git paths from `chezmoi/.chezmoiignore`, including its older work-only `personal.inc` exclusion, when chezmoi is retired or its inability to touch these paths is otherwise established. They are ownership protection while both systems coexist, not runtime Git behavior.
- [ ] **Mixed Ansible/native dispatcher.** Remove Ansible tag partitioning and execution from `mise.toml`'s `reconcile:laptop`, plus the Ansible branch of `scripts/list-tags.sh`, after every remaining laptop capability is native. Replace mixed-routing tests with native-only routing coverage. Do not remove daily mise maintenance or scoped authentication still required by native resources.
- [ ] **Ansible-owned installation/authentication dependencies.** Migrate the remaining consumers of `ansible/roles/mise` and `ansible/sudo-askpass.sh` before deleting them. Native theme apply still uses askpass; its directory name does not make it dead code.
- [ ] **Work private configuration inventory and final notice.** At the end, update `README.work.md` with the required configuration migration notice and exact old-to-new private-file instructions. Reconcile it against the actual work checkout, not just the tracked repository. Delete obsolete private templates/data only after their last consumer has migrated and before/after behavior has been verified.

## Keep

Native managed blocks and Tera templates, shared capability declarations and symlinks, Git input validation, first-run theme state initialization, watcher runtime-input hashing, SSH lease lifecycle, and once-daily latest-stable mise maintenance are permanent behavior. The host-wide `vars.host_profile` (`personal` or `work`) is shared context; capability roles such as theme `detector`/`mirror` remain separate.
