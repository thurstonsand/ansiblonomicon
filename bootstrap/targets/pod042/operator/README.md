# Operator environment

`operator/mise.toml` is the operator's global runtime and utility inventory. `mise.operator.toml` declares Debian packages and links that global mise config into the operator's home before setup, while bootstrap directories retain explicit operator ownership.

Base owns the zsh package and the operator's `/usr/bin/zsh` login shell; the driver applies base packages before accounts, so the account is never created with a shell path that has not been installed.

The remaining installation steps are named mise tasks, ordered through dependencies:

1. `operator:tools`: install and update the inventory, reconcile npm globals beside Node, and refresh shims.
2. `operator:agents`: install missing vendor-native agent CLIs and reconcile T3's standalone release.
3. `operator:sessions`: build the sessions CLI from `bootstrap/capabilities/software/sources/sessions/` when its Go sources change.

Terminal configuration, TPM, and plugins are owned by the `terminal-tools` capability, which runs after the prerequisite bootstrap during a full reconciliation.

Agent installation follows the official installers: [Amp](https://ampcode.com/install.sh), [Claude](https://claude.ai/install.sh), [Codex](https://chatgpt.com/codex/install.sh), [OpenCode](https://opencode.ai/install), and [T3](https://t3.codes/install.sh). The task checks stable executable paths before downloading. Amp lives at `~/.amp/bin/amp`, linked from `~/.local/bin/amp`; Claude and Codex live in `~/.local/bin`; OpenCode lives in `~/.opencode/bin`. T3's checksum-verified standalone archive lives under `~/.t3/runtime/versions/`, linked from `~/.local/bin/t3`; reconciliation downloads only when that link differs from the latest stable release. This avoids npm pruning T3's optional platform bundle during repeat installs. Enrollment remains in the same `~/.t3` home. The installer environment puts native directories first on PATH and OpenCode receives `--no-modify-path`, leaving shell configuration to the native `shell` capability. No agent uses mise's npm backend or trust-policy exceptions.

T3's stable version is resolved through GitHub's public `releases/latest` redirect and passed explicitly to its installer. This avoids the unauthenticated GitHub API quota during reconciliation; release archives still receive the vendor's checksum verification. Service changes remain in `remote-development`, which has access to the user's systemd session.

The final hook runs those tasks as `thurstonsand` with an isolated environment. It does not load the project's credential hook or replace the base bootstrap task.

Bootstrap owns software installation and service lifecycle. The shared native `shell`, `terminal-theme`, `terminal-tools`, `git-client`, `jj-client`, `neovim`, and `agent-harness`/`agent-config` capabilities own shell, terminal, VCS, Neovim, and agent configuration on pod042 and laptops; full reconciliation applies them after operator prerequisites. Focused VCS reconciliation loads shared identity facts and changes only the selected client's configuration.

T3 and Amp enrollment and persistence belong to `remote-development`, not this capability. T3 serves multiple projects from the operator's home; Amp's runner belongs to this checkout.
