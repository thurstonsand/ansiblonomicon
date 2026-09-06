# Operator environment

`operator/mise.toml` is the operator's global runtime and utility inventory. `mise.operator.toml` declares Debian packages, the global mise config needed to install chezmoi, the sessions binary directory, and TPM's checkout.

The remaining installation steps are named mise tasks, ordered through dependencies:

1. `operator:tools`: install and update the inventory, reconcile npm globals beside Node, including T3, and refresh shims.
2. `operator:agents`: install missing vendor-native agent CLIs, then retire their old mise-managed installations without removing authentication directories.
3. `operator:sessions`: build the existing sessions CLI when its Go sources change.
4. `operator:dotfiles`: initialize and apply the full repository's chezmoi source.
5. `operator:tmux`: install the plugins declared by the applied tmux config.

Agent installation follows the official installers: [Amp](https://ampcode.com/install.sh), [Claude](https://claude.ai/install.sh), [Codex](https://chatgpt.com/codex/install.sh), and [OpenCode](https://opencode.ai/install). The task checks their stable executable paths before downloading; installed agents keep their vendor update mechanisms. Amp lives at `~/.amp/bin/amp`, linked from `~/.local/bin/amp`; Claude and Codex live in `~/.local/bin`; OpenCode lives in `~/.opencode/bin`. The installer environment puts native directories first on PATH and OpenCode receives `--no-modify-path`, leaving shell configuration to chezmoi. T3 uses its supported `npm install -g t3` route through mise-managed Node and updates with the other npm globals. No agent uses mise's npm backend or trust-policy exceptions.

The final hook runs those tasks as `thurstonsand` with an isolated environment. It does not load the project's credential hook or replace the base bootstrap task.

Bootstrap owns software installation and service lifecycle. Chezmoi owns user configuration, including the shell, editor, and terminal-theme files. Pod042's theme templates reuse the existing role sources; the legacy role still owns their deployment on other hosts.

T3 and Amp enrollment and persistence belong to `remote-development`, not this capability. T3 serves multiple projects from the operator's home; Amp's runner belongs to this checkout. Harness-managed skill catalogues remain a separate migration item.
