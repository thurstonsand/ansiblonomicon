# Operator environment

`operator/mise.toml` is the operator's global runtime and utility inventory. `mise.operator.toml` declares Debian packages, the global mise config needed to install chezmoi, and the sessions binary directory.

Base owns the zsh package and the operator's `/usr/bin/zsh` login shell; the driver applies base packages before accounts, so the account is never created with a shell path that has not been installed.

The remaining installation steps are named mise tasks, ordered through dependencies:

1. `operator:tools`: install and update the inventory, reconcile npm globals beside Node, install T3's CLI into its own prefix, and refresh shims.
2. `operator:agents`: install missing vendor-native agent CLIs, then retire their old mise-managed installations without removing authentication directories.
3. `operator:sessions`: build the existing sessions CLI when its Go sources change.
4. `operator:dotfiles`: initialize and apply the full repository's chezmoi source.

Terminal configuration, TPM, and plugins are owned by the `terminal-tools` capability, which runs after the prerequisite bootstrap during a full reconciliation.

Agent installation follows the official installers: [Amp](https://ampcode.com/install.sh), [Claude](https://claude.ai/install.sh), [Codex](https://chatgpt.com/codex/install.sh), and [OpenCode](https://opencode.ai/install). The task checks their stable executable paths before downloading; installed agents keep their vendor update mechanisms. Amp lives at `~/.amp/bin/amp`, linked from `~/.local/bin/amp`; Claude and Codex live in `~/.local/bin`; OpenCode lives in `~/.opencode/bin`. The installer environment puts native directories first on PATH and OpenCode receives `--no-modify-path`, leaving shell configuration to the native `shell` capability. T3 is the exception to the npm globals: it installs with `npm install --prefix ~/.t3/cli` under T3's own npmrc. A global install runs npm's implicit `node-gyp rebuild` for `msgpackr-extract`'s `binding.gyp`, which no allow-scripts policy gates and this host, lacking node-gyp, cannot satisfy ([#7475](https://github.com/pingdotgg/t3code/issues/7475) is the same family). The prefix install blocks that script and still builds node-pty, which the npmrc allows. `npx` is T3's documented route but exports `npm_config_allow_scripts` into the pinned-runtime install, which then rejects it ([#9398](https://github.com/pingdotgg/t3code/issues/9398)). No agent uses mise's npm backend or trust-policy exceptions.

The final hook runs those tasks as `thurstonsand` with an isolated environment. It does not load the project's credential hook or replace the base bootstrap task.

Bootstrap owns software installation and service lifecycle. The shared native `shell`, `terminal-theme`, `terminal-tools`, `git-client`, `jj-client`, and `neovim` capabilities own shell, terminal, VCS, and Neovim configuration on pod042 and both Macs; full reconciliation applies them after operator prerequisites. Focused VCS reconciliation loads shared identity facts and changes only the selected client's configuration. Chezmoi still owns the remaining application and agent dotfiles.

T3 and Amp enrollment and persistence belong to `remote-development`, not this capability. T3 serves multiple projects from the operator's home; Amp's runner belongs to this checkout. Harness-managed skill catalogues remain a separate migration item.
