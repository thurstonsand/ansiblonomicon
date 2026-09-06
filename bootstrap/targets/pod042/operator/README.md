# Operator environment

`operator/mise.toml` is the operator's global tool inventory. `mise.operator.toml` declares Debian packages, the global mise config needed to install chezmoi, the sessions binary directory, and TPM's checkout.

The remaining installation steps are named mise tasks, ordered through dependencies:

1. `operator:tools`: install and update the inventory, reconcile npm globals beside Node, and refresh shims.
2. `operator:sessions`: build the existing sessions CLI when its Go sources change.
3. `operator:dotfiles`: initialize and apply the full repository's chezmoi source.
4. `operator:tmux`: install the plugins declared by the applied tmux config.

The final hook runs those tasks as `thurstonsand` with an isolated environment. It does not load the project's credential hook or replace the base bootstrap task.

Bootstrap owns software installation and service lifecycle. Chezmoi owns user configuration, including the shell, editor, and terminal-theme files. Pod042's theme templates reuse the existing role sources; the legacy role still owns their deployment on other hosts.

T3 and Amp enrollment and persistence belong to `remote-development`, not this capability. T3 serves multiple projects from the operator's home; Amp's runner belongs to this checkout. Harness-managed skill catalogues remain a separate migration item.
