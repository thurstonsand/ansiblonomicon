# Operator environment

`operator/mise.toml` is the operator's global runtime and utility inventory. `mise.operator.toml` declares Debian packages, the global mise config needed to install chezmoi, the sessions binary directory, and TPM's checkout.

Base owns the zsh package and the operator's `/usr/bin/zsh` login shell; the guarded driver applies base packages before accounts, including on first access, so SSH never receives a shell path that has not been installed.

The remaining installation steps are named mise tasks, ordered through dependencies:

1. `operator:tools`: install and update the inventory, reconcile npm globals beside Node, install T3's CLI into its own prefix, and refresh shims.
2. `operator:agents`: install missing vendor-native agent CLIs, then retire their old mise-managed installations without removing authentication directories.
3. `operator:sessions`: build the existing sessions CLI when its Go sources change.
4. `operator:dotfiles`: initialize and apply the full repository's chezmoi source.
5. `operator:tmux`: install the plugins declared by the applied tmux config.

Agent installation follows the official installers: [Amp](https://ampcode.com/install.sh), [Claude](https://claude.ai/install.sh), [Codex](https://chatgpt.com/codex/install.sh), and [OpenCode](https://opencode.ai/install). The task checks their stable executable paths before downloading; installed agents keep their vendor update mechanisms. Amp lives at `~/.amp/bin/amp`, linked from `~/.local/bin/amp`; Claude and Codex live in `~/.local/bin`; OpenCode lives in `~/.opencode/bin`. The installer environment puts native directories first on PATH and OpenCode receives `--no-modify-path`, leaving shell configuration to chezmoi. T3 is the exception to the npm globals: it installs with `npm install --prefix ~/.t3/cli` under T3's own npmrc. A global install runs npm's implicit `node-gyp rebuild` for `msgpackr-extract`'s `binding.gyp`, which no allow-scripts policy gates and this host, lacking node-gyp, cannot satisfy ([#7475](https://github.com/pingdotgg/t3code/issues/7475) is the same family). The prefix install blocks that script and still builds node-pty, which the npmrc allows. `npx` is T3's documented route but exports `npm_config_allow_scripts` into the pinned-runtime install, which then rejects it ([#9398](https://github.com/pingdotgg/t3code/issues/9398)). No agent uses mise's npm backend or trust-policy exceptions.

The final hook runs those tasks as `thurstonsand` with an isolated environment. It does not load the project's credential hook or replace the base bootstrap task.

Bootstrap owns software installation and service lifecycle. Chezmoi owns user configuration, including the shell, editor, and terminal-theme files. Pod042's theme templates reuse the existing role sources; the legacy role still owns their deployment on other hosts.

T3 and Amp enrollment and persistence belong to `remote-development`, not this capability. T3 serves multiple projects from the operator's home; Amp's runner belongs to this checkout. Harness-managed skill catalogues remain a separate migration item.
